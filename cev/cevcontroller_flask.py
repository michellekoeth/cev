from flask import Flask, render_template as template, request, make_response, redirect, flash, url_for, session, jsonify, send_from_directory
from celery import Celery
from celery.contrib import rdb
# might need this later if I use SQL db connections
#abort from flask.ext.sqlalchemy import SQLAlchemy
import POSPatentTagger as ptag
import spacynlplib as spacylib
import claimevlib as cevlib
import scraperlib as slib
from mechanize import Browser
import string
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import csv
import re
import math
import traceback
import os
import random
import sqlite3
from sqlite3 import Error
import json
import difflib

app = Flask(__name__)
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
# So celery can store status and results from tasks
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

def create_connection(db_file):
	# create a database connection to the SQLite database
	try:
		conn = sqlite3.connect(db_file)
		return conn
	except Error as e:
		print(e)

	return None

def get_PTAB_decision(appealnowithdash):
    # Remove the dash since the PTAB FOIA form wont accept it in this format
    PTAB_url = "https://e-foia.uspto.gov/Foia/PTABReadingRoom.jsp"
    appealno = appealnowithdash[0:4] + appealnowithdash[5:]
    # The PTAB decision form has submit js, so cant use mechanize, so use selenium with phantomjs:
    # Prod path:
    driver = webdriver.PhantomJS(executable_path = "/home/cev/projects/cevenv/share/phantomjs-2.1.1-linux-x86_64/bin/phantomjs")
    # dev path:
    #driver = webdriver.PhantomJS(executable_path = "/Applications/phantomjs-2.1.1-macosx/bin/phantomjs")
    driver.get(PTAB_url)
    identifier_type_select = driver.find_element_by_name("Objtype")
    for opt in identifier_type_select.find_elements_by_tag_name('option'):
        if opt.text == 'Appeal No':
            opt.click()
            break
    appealno_input = driver.find_element_by_name("SearchId")
    appealno_input.send_keys(appealno)
    # This should submit the query, and the result page will now load into the driver
    appealno_input.submit()
    # Find the application number link on the resulting page and return the link from the function
    # The link is unique in that it has a target attribute = "_self"
    link_element_to_pdf = driver.find_element_by_xpath('//a[@target="_self"]')
    PDF_link = link_element_to_pdf.get_attribute("href")
    return PDF_link

@celery.task(bind=True)
def getMatchedClaimsCelery(self,inputfn,preamblgowordsfn,mistaggedrulesfn,transphrasefn):
	taskidentifier = self.request.id
	celerytask = self
	self.update_state(state="PROGRESS", meta={'current':0, 'total':0, 'status':"Just started!"})
	outputfilename = "csv/MatchedClaimset_" + str(taskidentifier)+".csv"
	slib.matched_claims_from_pat_app_claimlist(inputfn,outputfilename,preamblegowordsfn,mistaggedrulesfn, transphrasefn, celerytask)
	return {'current': 0, 'status':'Task Completed!', outputfn: outputfilename}

# This Celery task is for the Get_Patent_List Self-Service Job Type
@celery.task(bind=True)
def getLongPatentList(self, query):
	taskidentifier = self.request.id
	self.update_state(state="PROGRESS", meta={'current':0, 'total':0, 'status':"Just started, have not fetched patent list yet"})
	#Advanced search home page from PatFT
	indexurl = "http://patft.uspto.gov/netahtml/PTO/search-adv.htm"
	# celery debugging
	#rdb.set_trace()
	pgpubnos = []
	driver = webdriver.PhantomJS(executable_path = "/home/cev/projects/cevenv/share/phantomjs-2.1.1-linux-x86_64/bin/phantomjs")
	driver.get(indexurl)
	querybox = driver.find_element_by_name("Query")
	# hard coded query for now just to test background task processing
	querybox.send_keys(query)
	# This should submit the query, and the result page will now load into the driver
	querybox.submit()
	flag = 0
	totalnum = 0
	strongtags = driver.find_elements_by_tag_name('strong')
	message2 = ""
	totalnum = strongtags[2].text
	# Now we calculate how many pages of results there will be
	pagesofresults = math.ceil(float(totalnum)/50)     
	self.update_state(state="PROGRESS", meta={'current':1, 'total':int(totalnum), 'status':"Loaded in first PATFT Page"})
	mtotal = 0
	for ind in range(int(pagesofresults)): 
		tags = driver.find_elements_by_tag_name('a')
		for tagtext in tags:
			# Only get non Rexam, utility patent numbers. The below RegEx extracts just those patent numbers
			m = re.search('\\d{1}[,]\d{3}[,]\d{3}', tagtext.text)
			if m:
				pgpub = m.group(0)
				pgpub = pgpub[0]+pgpub[2:5]+pgpub[6:]
				if pgpub not in pgpubnos:
					pgpubnos.append(pgpub)
					mtotal += 1
				self.update_state(state="PROGRESS",
								  meta={'current':mtotal, 'total':int(totalnum), 'status':"Processed a patent!"})
		while True:
			try:
				#Time for page to load in
				driver.find_element_by_name('StartNum').send_keys(str(((ind+1)*50)+1))
				#print "Start next at: " + str(((ind+1)*50)+1)
				driver.find_element_by_name("StartAt").click()
				# In theory now the next page should be loaded in
				# give it time to load in
				time.sleep(2)
				message2 = "Just loaded a new page of results!"
				self.update_state(state="PROGRESS",
								  meta={'current':(ind*50), 'total':int(totalnum), 'status':message2})
				break
			except:
				traceback.print_exc()
				print "PatFT is *mad* - Waiting 30 sec before next query!"
				time.sleep(30)
	# Now write data to CSV
	file2writeto = "csv/patlist" + taskidentifier+".csv"
	with open(file2writeto, 'w') as csvfile:
		fieldnames = ['pat_no_'+query]
		writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
		writer.writeheader()
		for pub in pgpubnos:
			writer.writerow({'pat_no_'+query: pub})
	return {'current': len(pgpubnos), 'total':len(pgpubnos), 'status':'Task Completed!','result':42}

# This Celery task is for the Patent_And_PgPub_Claimsets_from_file Self-Service Job Type
@celery.task(bind=True)
def createClaimsFile(self, query):
	taskidentifier = self.request.id
	file2writeto = "csv/patappclaimlist" + taskidentifier+".csv"
	# First write the headers to our output file
	with open(file2writeto, 'w') as csvfile:
		fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
		writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
		writer.writeheader()
	# Read in each patent from the input file and process for a claimset
	numofpatsprocessed = 0
	rowno = 0
	fileandpath = "csv/"+query
	totallines = len(open(fileandpath).readlines())
	with open(fileandpath, 'rb') as csvfile:
		reader = csv.reader(csvfile, delimiter=',')
		reader.next() # skip header row 
		for row in reader:
			rowno += 1
			statusnow = "Pat No: " + str(row[0]) + " now being processed"
			self.update_state(state="PROGRESS", meta={'current':rowno, 'total':totallines, 'status':statusnow})
			returnhash = ptag.getOnePatAppClaimset(row[0])
			if returnhash <> 0:
				numofpatsprocessed += 1
				patno = returnhash['patno']
				appno = returnhash['appno']
				patclaims = returnhash['patclaims']
				appclaims = returnhash['appclaims']
				# so patent had a pgpub, and both corresponding claimsets were returned
				# Write out all of the claims row by row into the CSV file
				with open(file2writeto, 'a') as csvfile:
					fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
					writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
					for claim in patclaims:
						writer.writerow({'pat_no': patno, 'app_no':appno, 'pat_claim':claim, 'app_claim':""})
					for claim in appclaims:
						writer.writerow({'pat_no': patno, 'app_no':appno, 'pat_claim':"", 'app_claim':claim})
	return {'current': 0, 'numofpats':numofpatsprocessed, 'status':'Task Completed!'}

@app.route('/getClaims', methods=["POST"])
def getClaims():
	q = request.form.get('patentlistfile')
	task = createClaimsFile.delay(q)
	taskid = str(task.id)
	return template ("cev_submitjob.html",whatid=taskid, jobtype="Patent_And_PgPub_Claimsets_from_file")

@app.route('/')
def index():
	output = template('cev_homepage.html')
	return output

@app.route('/rawclaimdiff')
def rawclaimdiff():
	output = template('cev_homepage.html')
	return output

@app.route('/hotspeechparts')
def hotspeechparts():
	output = template('cev_hotwords.html')
	return output

@app.route('/', methods=["POST"])
def getClaimDiffViz():
	docid = request.form.get('docid')
	# Run claim viz code here
	h2rdict = get_matched_and_differences_for_a_patno(docid)
	return template("cev_displayclaimdiff.html",claimviz=h2rdict['html'],patentno=docid,appno=h2rdict['appno'])

def get_matched_and_differences_for_a_patno(patno):
	html = ""
	# First get the set of matched claims:
	returnhash = ptag.getOnePatAppClaimset(patno)
	if returnhash:
		appno = returnhash['appno']
		patclaims = returnhash['patclaims']
		appclaims = returnhash['appclaims']
		# Now match the claimsets to extract matched independent claims
		matcheddict = spacylib.matched_claimset_basic(patclaims,appclaims)
		retarray = matcheddict['claimpairs']
		for matchedpair in retarray:
			# compare pat claim [1] to appclaim [0]
			html = html + "<br><br>" + show_diff(matchedpair[1],matchedpair[0])
	else:
		html = "No corresponding PgPub was found for Patent No. " + str(patno) + ". Accordingly, no claim comparison can be made at this time."
		appno = "No corresponding PgPub found"

	return {"html":html,"appno":appno}

def show_diff(text, n_text):
    """
    http://stackoverflow.com/a/788780
    Unify operations between two compared strings seqm is a difflib.
    SequenceMatcher instance whose a & b are strings
    """
    seqm = difflib.SequenceMatcher(None, text, n_text)
    output= []
    for opcode, a0, a1, b0, b1 in seqm.get_opcodes():
        if opcode == 'equal':
            # MMK: I added the below conditional because otherwise this alg was shifting the red input text by a letter for when
            # the first letter of a word matches in both strings, but the word itself doesn't match
            if ((seqm.a[a1-1] == seqm.b[b1-1]) and (seqm.a[a1-2] == " ")):
                output.append(seqm.a[a0:a1-1])
            else:
                output.append(seqm.a[a0:a1])
        elif opcode == 'insert':
            # MMK: I added the below conditional because otherwise this alg was shifting the red input text by a letter for when
            # the first letter of a word matches in both strings, but the word itself doesn't match
            if ((seqm.b[b0-1] == seqm.a[a0-1]) and (seqm.b[b0-2] == " ")):
                output.append("<font color=red>" + seqm.b[b0-1:b1-1] + "</font>"+seqm.b[b0-1])
            else:
                output.append("<font color=red>" + seqm.b[b0:b1] + "</font>")
        elif opcode == 'delete':
            output.append("<font color=blue>" + seqm.a[a0:a1] + "</font>")
        elif opcode == 'replace':
            # seqm.a[a0:a1] -> seqm.b[b0:b1]
            output.append("<font color=green>" + seqm.b[b0:b1] + "</font>")
        else:
            raise RuntimeError, "unexpected opcode"
    return ''.join(output)

@app.route('/claimextract')
def claimextract():
	output = template('cev_claimextract.html')
	return output

@app.route('/status/<task_id>/<jobtype>')
def taskstatus(task_id,jobtype):
	# Upon task completion, the cev_successjob.html expects to receive the following parameters to report to the user:
	# whatid (job id), jobtype, fyi (result message depending on job), file2download (the resulting CSV output file)
	if jobtype == 'Get_Patent_List':
		task = getLongPatentList.AsyncResult(task_id)
		if task.state == 'SUCCESS':
			f2d = "patlist" + str(task_id)
			fyi = "Total number of patent numbers obtained is: " + str(task.info.get('total', 1))
			return template ("cev_successjob.html",whatid=task_id,fyi=fyi,jobtype=jobtype,file2download=f2d)	
		elif task.state == 'PROGRESS':
			total = str(task.info.get('total', 1))
			if total <> "0":
				currstatus = "Job is still pending. The progress is " +str(task.info.get('current', 0)) + " records out of a total of " + str(task.info.get('total', 0)) +" records are complete."
			else:
				currstatus = str(task.info.get('status', ''))
			return template ("cev_incompletejob.html",whatid=task_id,currstatus=currstatus,jobtype=jobtype)
		else: # You would get here if there was an error of some sort. the info.get gets the specified key from the meta hash
			response = {'state': task.state,'current': task.info.get('current', 0),'total': task.info.get('total', 1),'status': task.info.get('status', '')}
			if 'result' in task.info:
				response['result'] = task.info['result']
			return jsonify(response)
	if jobtype == 'Patent_And_PgPub_Claimsets_from_file':
		task = createClaimsFile.AsyncResult(task_id)
		if task.state == 'PENDING':
			return template ("cev_incompletejob.html",whatid=task_id,currstatus="Job has not started - still pending! ",jobtype=jobtype)
		elif task.state == 'SUCCESS':
			f2d = "patappclaimlist"+str(task_id)
			fyi = "In total, " + str(task.info.get('numofpats', 1)) +" patents were processed for their claims, and the corresponding PgPub's claims."
			return template ("cev_successjob.html",whatid=task_id,fyi=fyi,jobtype="Get Patent/PgPub Claims",file2download=f2d)
		elif task.state == "PROGRESS":
			currstatus = "The progress so far is " + str(task.info.get('current', 0)) + " records processed out of a total of: " + str(task.info.get('total', 0))
			return template ("cev_incompletejob.html",whatid=task_id,currstatus=currstatus,jobtype=jobtype)
		elif task.state != 'FAILURE':
			response = {'state': task.state,'current': task.info.get('current', 0),'total': task.info.get('total', 1),'status': task.info.get('status', '')}
			if 'result' in task.info:
				response['result'] = task.info['result']
				return jsonify(response)
		else:
			# something went wrong in the background job
			response = {'state': task.state,'current': 1,'total': 1,'status': str(task.info)}  # this is the exception raised
			return jsonify(response)
	if jobtype == 'Get_Matched_Claims':
		# {'current': 0, 'status':'Task Completed!', outputfn: outputfilename}
		task = getLongPatentList.AsyncResult(task_id)
		if task.state == 'SUCCESS':
			f2d = str(task.info.get('outputfn',''))
			qty = str(task.info.get('total', 1))
			fyi = "Your Matching Claimsets job has successfully completed!"
			return template ("cev_successjob.html",whatid=task_id,fyi=fyi,jobtype=jobtype,file2download=f2d)	
		elif task.state == 'PROGRESS':
			total = str(task.info.get('total', 1))
			if total != "0":
				currstatus = "Job is still pending. The progress is " +str(task.info.get('current', 0)) + " records out of a total of " + str(task.info.get('total', 0)) +" records are complete."
			else:
				currstatus = str(task.info.get('status', ''))
			return template ("cev_incompletejob.html",whatid=task_id,currstatus=currstatus,jobtype=jobtype)
		else: # You would get here if there was an error of some sort. the info.get gets the specified key from the meta hash
			response = {'state': task.state,'current': task.info.get('current', 0),'total': task.info.get('total', 1),'status': task.info.get('status', '')}
			if 'result' in task.info:
				response['result'] = task.info['result']
			return jsonify(response)

@app.route('/csvfile/<filename>')
def servecsvfile(filename):
	return send_from_directory(directory="csv/", filename=filename)

	
@app.route('/getPatents', methods=["POST"])
def getClaimSet():
	# run this as a background thread using celery in case it takes too long
	q = request.form.get('patftquery')
	task = getLongPatentList.delay(q)
	taskid = str(task.id)
	return template ("cev_submitjob.html",whatid=taskid,jobtype="Get_Patent_List")

@app.route('/getMatchedClaims', methods=["POST"])
def getMatchedClaims():
	# run this as a background thread using celery in case it takes too long
	inputfn = request.form.get('matchedquery')
	trainingsm = request.form.get('trainingsm')
	if trainingsm == "2630":
		preamblgowordsfn = "csv/preamblegowords2630.csv"
		mistaggedrulesfn = "csv/mistagrules2630.csv"
		transphrasefn =  "csv/transphrases2630.csv"
	task = getMatchedClaimsCelery(inputfn,preamblgowordsfn,mistaggedrulesfn,transphrasefn)
	taskid = str(task.id)
	return template ("cev_submitjob.html",whatid=taskid,jobtype="Get_Matched_Claims")

@app.route('/getHotPOSViz', methods=["POST"])
def getHotPOSViz():
	# get the selected file value, we need to pass this to the D3 code
	fn = request.form.get('posinputfile')
	return template("cev_hotposd3viz.html",fn=fn)

@app.route('/hotwords')
def hotwords():
	# Get list of files in csv directory with _hotpos suffix. This will build the list of options
	file_list = []
	for file in os.listdir("/var/www/html/cev/cev/csv"):
		if file.endswith("_hotpos.csv"):
			file_list.append(file)
	return template('cev_hotwords.html',server_list=file_list)


@app.route('/chek112f/<claimterm>')
def chek112f(claimterm):
	database = "/home/cev/projects/onetwelvef.db"
	# create a database connection
	flag = 0
	link = ""
	with create_connection(database) as conn:
		cur = conn.cursor()
		t = (claimterm,)
		cur.execute("SELECT * FROM one12fcases where [Term at Issue] = ?",t)
		rows = cur.fetchall()
	termlist = []
	for row in rows:
		if row[6] == None:
			link = get_PTAB_decision(row[1])
			flag = 1
		else:
			link = row[6]
		termDict = {
			'Case_title':row[0],
			'Appeal_num':row[1],
			'Opinion_year':row[2],
			'Term':row[3],
			'112_f_Applied':row[4],
			'Commentary':row[5],
			'Link_to_Decision_PDF':link
			}
		termlist.append(termDict)
		if flag:
			with create_connection(database) as conn:
				cur = conn.cursor()
				cur.execute("UPDATE one12fcases SET Decision_PDF_Link = ? WHERE Cite = ?",(link,row[1]))
			flag = 0
	return json.dumps(termlist)

@app.route('/all112fPTABterms')
def all_112f_PTAB_terms():
	database = "/home/cev/projects/onetwelvef.db"
	with create_connection(database) as conn:
		cur = conn.cursor()
		cur.execute("SELECT * FROM one12fcases")
		rows = cur.fetchall()
	termlist = []
	for row in rows:
		termDict = {
			'Title':row[0],
			'Cite':row[1],
			'Year':row[2],
			'Term at Issue':row[3],
			'112(f)?':row[4],
			'Useful Dicta':row[5],
			'Decision_PDF_Link':row[6]
			}
		termlist.append(termDict)
	return json.dumps(termlist)


if __name__ == "__main__":
    app.run(host="0.0.0.0")

