#!/usr/bin/env python
# Scraperlib.py Scraper library for PatFT and AppFT - for use with Ubuntu OS
# dont need the display unless you want to see the browser I think
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import csv
import re
import math
import time
import traceback
import os

def select_form(form):
    return form.attrs.get('name', None) == 'srchForm2'

def getPatListToFile(query):
    #Advanced search home page from PatFT
    indexurl = "http://patft.uspto.gov/netahtml/PTO/search-adv.htm"
    pgpubnos = []
    # if running code locally in dev, use the following to find phantomjs path
    #driver = webdriver.PhantomJS(executable_path = "/Applications/phantomjs-2.1.1-macosx/bin/phantomjs")
    driver = webdriver.PhantomJS(executable_path = "/home/cev/projects/cevenv/share/phantomjs-2.1.1-linux-x86_64/bin/phantomjs")
    driver.get(indexurl)
    querybox = driver.find_element_by_name("Query")
    querybox.send_keys(query)
    # This should submit the query, and the result page will now load into the driver
    querybox.submit()
    flag = 0
    totalnum = 0
    strongtags = driver.find_elements_by_tag_name('strong')
    totalnum = strongtags[2].text
    # Now we calculate how many pages of results there will be
    pagesofresults = math.ceil(float(totalnum)/50)     
    for ind in range(int(pagesofresults)): 
        tags = driver.find_elements_by_tag_name('a')
        for tagtext in tags:
            m = re.search('\\d{1}[,]\d{3}[,]\d{3}', tagtext.text)
            if m:
                pgpub = m.group(0)
                pgpub = pgpub[0]+pgpub[2:5]+pgpub[6:]
                if pgpub not in pgpubnos:
                    pgpubnos.append(pgpub)
                    #print pgpub
        while True:
            try:
                #Time for page to load in
                driver.find_element_by_name('StartNum').send_keys(str(((ind+1)*50)+1))
                #print "Start next at: " + str(((ind+1)*50)+1)
                driver.find_element_by_name("StartAt").click()
                # In theory now the next page should be loaded in
                # give it time to load in
                time.sleep(2)
                break
            except:
                traceback.print_exc()
                print "PatFT is *mad* - Waiting 15 sec before next query!"
                time.sleep(15)

    # Now write data to CSV
    timestr = str(time.time())
    file2writeto = "patlist" + timestr+".csv"
    with open(file2writeto, 'w') as csvfile:
        fieldnames = ['pat_no']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for idx, pub in enumerate(pgpubnos):
            writer.writerow({'pat_no': pub})    

    return True