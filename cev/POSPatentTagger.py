#!/usr/bin/env python

#import operator
import re
from mechanize import Browser
import spacy
import csv
import time

############################################################################################
# Removes wierd spacing from PatFT/AppFT claim sets, makes new tag called CLMN for claim number
##############################################################################################
def CleanTagged(taggedtuplelist):
    fixedtaglist = []
    for tagtuple in taggedtuplelist:
        if re.match('\d+\.', tagtuple[0]):
            clmno = re.match('\d+\.', tagtuple[0]).group(0)
            # remove the period after the claim number
            clmno = clmno[:-1]
            # Fix the tag to be a custom "CLMN" tag
            fixedtag = (str(clmno), "CLMN")
        elif tagtuple[0].endswith("."):
            fixedtag = (str(tagtuple[0][:-1]), str(tagtuple[1]))
        else:
            fixedtag = (str(tagtuple[0]),str(tagtuple[1]))
        print str(fixedtag)
        fixedtaglist.append(fixedtag)
    return fixedtaglist


####################################################################################
# Given a docid (pat or app pub) and section type (either claims or description),
# returns the text from the requested section. Is a large string if a description is requested
# or is a list of strings (each string being a claim) if claims are requested, is a string if "priorpub" requested
# if "pgpub_and_claims" is requested, the pgpub and claims are returned in a dictionary data structure
# key "pgppubno" contains the pgpub number, and key "claimslist" is a list of claims, 
# key "appnumber" returns the US application (serial) number
# NOTE: If ran too often, this function chokes PatFT or AppFT. So always run bulk jobs in a try/except clause
###################################################################################
def getPatDocSection(docid,sectiontypestr):
    # First get the PATFT or APPFT URL and set a flag to remember if it is a patent or app
    URL = ""
    doctype = ""
    if re.search("\\d{11}",docid):
        URL = "http://appft.uspto.gov/netacgi/nph-Parser?Sect1=PTO1&Sect2=HITOFF&d=PG01&p=1&u=%2Fnetahtml%2FPTO%2Fsrchnum.html&r=1&f=G&l=50&s1=%22" + docid + "%22.PGNR.&OS=DN/" + docid + "&RS=DN/" + docid
        doctype = "app"
        #print "processing app no:" + docid
    elif re.search("\\d{7}",docid):
        URL = "http://patft.uspto.gov/netacgi/nph-Parser?Sect1=PTO1&Sect2=HITOFF&d=PALL&p=1&u=%2Fnetahtml%2FPTO%2Fsrchnum.htm&r=1&f=G&l=50&s1=" + docid + ".PN.&OS=PN/" + docid + "&RS=PN/" + docid
        doctype = "patent"
        #print "processing patent no: " + docid
    # now call up the webpage using mechanize. 
    mech = Browser()
    mech.set_handle_robots(False)
    mech.set_handle_refresh(False)  # can sometimes hang without this
    mech.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    page = mech.open(URL)
    html = page.read()
    claimlistfull = []
    claimno =''
    pgpubno = ""
    if ((sectiontypestr == "claims") or (sectiontypestr =="pgpub_and_claims")): # Return a claimset from the requested docid or both claims & pgpub no
        if doctype == "app":
            appsplithtml = html.split("<CENTER><B><I>Claims</B></I></CENTER>")
            split = appsplithtml[1].split("<CENTER><B><I>Description</B></I></CENTER>")
        elif doctype == "patent":
            patsplithtml = html.split("<CENTER><b><i>Claims</b></i></CENTER>")
            split = patsplithtml[1].split("<CENTER><b><i>Description</b></i></CENTER>")
            if sectiontypestr == "pgpub_and_claims":
                if "Prior Publication Data" in html:
                    section = html.split("<CENTER><b>Prior Publication Data</b></CENTER>")
                    section = section[1].split("</TR> </TABLE>")
                    pub = re.findall("US\s{1}\d{11}\s{1}[A-Z][0-9]", section[0])
                    pgpubno = pub[0]
                else:
                    pgpubno = 0
        claimbody = split[0]
        claimslist = claimbody.split("<BR><BR>")[1:]
        if doctype == "patent":
            claimslist.pop(0)
        for claimstr in claimslist:
            # Get rid of \n from end of claim, after the period
            claimstr = re.sub('\.\\n','.',claimstr)
            # Now get rid of all other \n's
            claimsliststr = re.sub('\\n+',' ', claimstr)
            # Now get rid of the space before the claim number - first get the substring with the claim number
            if re.match('\s{1}\d+\.\s{2}', claimsliststr):
                claimno = re.match('\s{1}\d+\.\s{2}', claimsliststr).group(0)
                fixed = claimno[1:-1]
                claimsliststr = claimsliststr.replace(claimno, fixed)
            elif re.match('\s{1}\d+\.\s{1}', claimsliststr):
                claimno = re.match('\s{1}\d+\.\s{1}', claimsliststr).group(0)
                fixed = claimno[1:]
                claimsliststr = claimsliststr.replace(claimno, fixed)
            # Now get rid of triple spaces
            claimsliststr = claimsliststr.replace("      "," ")
            claimlistfull.append(claimsliststr)
        # Get rid of the _<HR>\n at the end of the last claim:
        if doctype == "patent":
            claimlistfull[-1] = claimlistfull[-1][:-6]
            return {'pgpubno':pgpubno, 'claimslist': claimlistfull}
        if doctype == "app":
            claimlistfull[-1] = claimlistfull[-1][:-10]
            return {'claimslist': claimlistfull}
    elif sectiontypestr == "description":
        if doctype == "app":
            appsplithtml = html.split("<CENTER><B><I>Description</B></I></CENTER>")
            split = appsplithtml[1].split("<BR><BR><CENTER><B>* * * * *</B></CENTER>")
        elif doctype == "patent":
            patsplithtml = html.split("<CENTER><b><i>Description</b></i></CENTER>")
            split = patsplithtml[1].split("<BR><BR><CENTER><b>* * * * *</b></CENTER>")
        descbody = split[0].replace("<BR><BR>","")
        descbody = descbody.replace("<HR>","")
        return descbody
    elif (doctype == "patent" and sectiontypestr == "priorpub"):
        if "Prior Publication Data" in html:
            section = html.split("<CENTER><b>Prior Publication Data</b></CENTER>")
            section = section[1].split("</TR> </TABLE>")
            pub = re.findall("US\s{1}\d{11}\s{1}[A-Z][0-9]", section[0])
            return pub[0]
        else:
            return 0
    elif (doctype == "patent" and sectiontypestr == "appnumber"):
        # Get beginning of desired section
        section = html.split("Appl. No.:")
        # Get ending of desired section
        section = section[1].split("</b></TD></TR>")
        # now section[0] is whats inbetween, use regex to get the actual text we want (app num)
        pub = re.findall("\d{2}\/\d{3},\d{3}", section[0])
        # Clean up the number to remove all slashes and commas
        messyappno = pub[0]
        appnotoreturn = messyappno[0:2] + messyappno[3:6] + messyappno[7:]
        return appnotoreturn
    elif (doctype == "app" and sectiontypestr == "appnumber"):
        # The differences between the app text and the patent text is lol --
        # Basically, some of the HTML tags are capitalized (like <B>) and for some reason
        # In the app number they dont include a comma to set off digit triples
        # Get beginning of desired section
        section = html.split("Appl. No.:")
        # Get ending of desired section
        section = section[1].split("</B></TD></TR>")
        # now section[0] is whats inbetween, use regex to get the actual text we want (app num)
        pub = re.findall("\d{2}\/\d{6}", section[0])
        # Clean up the number to remove all slashes and commas
        messyappno = pub[0]
        appnotoreturn = messyappno[0:2] + messyappno[3:]
        return appnotoreturn
    else:
        print "Unrecognized requested section type. Returning"
        return null
    
    
##########################################################################    
# Gets claims for a given docid and POSTags them using spaCy python tagger
##########################################################################
def POSPatentTagger(docid):
    claimtagged = []
    taggedclaimset = []
    claimslist = getPatDocSection(docid,"claims")
    for claimstr in claimslist:
        # POSTag with SpaCy
        nlp = spacy.load('en')
        doc = nlp(unicode(claimstr,'utf_8'))
        for word in doc:
            # this writes the tagged tuple for the word into a list. Three tuple items:
            # The text of the word, the lemma of the word and the tag of the word
            claimtagged.append((word.text, word.lemma_,word.tag_))
            #print(word.text, word.lemma, word.lemma_, word.tag, word.tag_, word.pos, word.pos_)
        # aggregate tagged claim into the set
        taggedclaimset.append(claimtagged)
    # Fresh and clean, number one tagged claimslist when it steps out on the scene!!
    return taggedclaimset

############################################################################################
# TODO: Function that returns the first independent method/apparatus/CRM (beuregard) or system
# claim given an input claimset and the claim type to find. 
############################################################################################


#########################################################################################
# Gets pgpub id (just the number part) given a patent number if a pgpub exists
#########################################################################################
def getAppNo(patno):
    # given a patent number, get the corresponding PgPub docid if one exists
    num = getPatDocSection(patno,"priorpub")
    if num <> 0:
        return num[3:14]
    else:
        return num
    
##########################################################################    
# Gets claims for a given patent doc, finds the corresponding claims from
# the PgPub (if one exists) and POSTags both claim sets using spaCy python tagger
##########################################################################
def PatPubClaimEvTag(patno):
    claimtagged = []
    pattaggedclaimset = []
    apptaggedclaimset = []
    returnset = getPatDocSection(patno,"pgpub_and_claims")
    patclaimslist = returnset['claimslist']
    if returnset['pgpubno'] <> 0:
        pgpubno = returnset['pgpubno'][3:14]
    else:
        pgpubno = returnset['pgpubno']
    appclaimslist = getPatDocSection(pgpubno,'claims')['claimslist']
    nlp = spacy.load('en')
    for claimstr in patclaimslist:
        # POSTag with SpaCy
        doc = nlp(unicode(claimstr,'utf_8'))
        for word in doc:
            # this writes the tagged tuple for the word into a list. Three tuple items:
            # The text of the word, the lemma of the word and the tag of the word
            claimtagged.append((word.text, word.lemma_,word.tag_))
            #print(word.text, word.lemma, word.lemma_, word.tag, word.tag_, word.pos, word.pos_)
        # aggregate tagged claim into the set
        pattaggedclaimset.append(claimtagged)
        claimtagged = []
    
    claimtagged = []
    for claimstr in appclaimslist:
        # POSTag with SpaCy
        doc = nlp(unicode(claimstr,'utf_8'))
        for word in doc:
            # this writes the tagged tuple for the word into a list. Three tuple items:
            # The text of the word, the lemma of the word and the tag of the word
            claimtagged.append((word.text, word.lemma_,word.tag_))
            #print(word.text, word.lemma, word.lemma_, word.tag, word.tag_, word.pos, word.pos_)
        # aggregate tagged claim into the set
        apptaggedclaimset.append(claimtagged)
        claimtagged = []
    # Fresh and clean, number one tagged claimslist when it steps out on the scene!!
    return {'PatClaims':pattaggedclaimset,"AppClaims":apptaggedclaimset,"PatClaimsUntagged":patclaimslist,"AppClaimsUntagged":appclaimslist}


##########################################################################
# PatPubClaimEv - only returns the text claim lists (not tagged) for a given patent num and
# its corresponding PgPub if there is one
##########################################################################
def PatPubClaimEv(patno):
    claimtagged = []
    pattaggedclaimset = []
    apptaggedclaimset = []
    returnset = getPatDocSection(patno,"pgpub_and_claims")
    patclaimslist = returnset['claimslist']
    if returnset['pgpubno'] <> 0:
        pgpubno = returnset['pgpubno'][3:14]
    else:
        pgpubno = returnset['pgpubno']
    appclaimslist = getPatDocSection(pgpubno,'claims')['claimslist']
    return {'PatClaims':patclaimslist,"AppClaims":appclaimslist}

####################################################################################
# Given a patent number, finds the claims for that patent, and the corresponding pgpub and its claims
# and writes everything out to a CSV file
# NOTE: If ran too often, this function chokes PatFT or AppFT. So always run bulk jobs in a try/except clause
###################################################################################
def getOnePatAppClaimset(patid):
    # First get the PATFT URL
    URL = "http://patft.uspto.gov/netacgi/nph-Parser?Sect1=PTO1&Sect2=HITOFF&d=PALL&p=1&u=%2Fnetahtml%2FPTO%2Fsrchnum.htm&r=1&f=G&l=50&s1=" + patid + ".PN.&OS=PN/" + patid + "&RS=PN/" + patid
    # now call up the webpage using mechanize. 
    mech = Browser()
    mech.set_handle_robots(False)
    mech.set_handle_refresh(False)  # can sometimes hang without this
    mech.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    page = mech.open(URL)
    html = page.read()
    claimlistfull = []
    appclaimslist = []
    patclaimslist = []
    concatclaim = ""
    claimno =''
    pgpubno = ""
    try:
        patsplithtml = html.split("<CENTER><b><i>Claims</b></i></CENTER>")
        split = patsplithtml[1].split("<CENTER><b><i>Description</b></i></CENTER>")
    except:
        print "PatFT is *mad* - Waiting 15 sec before next query!"
        time.sleep(15)
        try:
            page = mech.open(URL)
            html = page.read()
            patsplithtml = html.split("<CENTER><b><i>Claims</b></i></CENTER>")
            split = patsplithtml[1].split("<CENTER><b><i>Description</b></i></CENTER>")
        except:
            print "PatFT is REALLY *mad* - Waiting 60 sec before next query!"
            time.sleep(60)
            page = mech.open(URL)
            html = page.read()
            patsplithtml = html.split("<CENTER><b><i>Claims</b></i></CENTER>")
            split = patsplithtml[1].split("<CENTER><b><i>Description</b></i></CENTER>")
    if "Prior Publication Data" in html:
        section = html.split("<CENTER><b>Prior Publication Data</b></CENTER>")
        section = section[1].split("</TR> </TABLE>")
        pub = re.findall("US\s{1}\d{11}\s{1}[A-Z][0-9]", section[0])
        pgpubno = pub[0]
    else:
        # Return a zero to indicate that the input patent number does not have a corresponding PgPub
        pgpubno = 0
        return 0
    claimbody = split[0]
    # Dividing the claim list by double BR will not always work (it will fail on really long claims that PATFt chunks into portions using brbr)
    # An example patent where this will fail is USPN 8,654,878. A better way to split the claimbody string is to regexp on numbers.. Or a combination of both
    # so for each BR section, LOOK for an intro number, else concatenate with the portion before..
    claimslist = claimbody.split("<BR><BR>")[1:]
    claimslist.pop(0)
    for idx, claimstr in enumerate(claimslist):
        # Get rid of \n from end of claim, after the period
        claimstr = re.sub('\.\\n','.',claimstr)
        # Now get rid of all other \n's
        claimsliststr = re.sub('\\n+',' ', claimstr)
        # Now get rid of the space before the claim number - first get the substring with the claim number
        if re.match('\s{1}\d+\.\s{2}', claimsliststr):
            claimno = re.match('\s{1}\d+\.\s{2}', claimsliststr).group(0)
            fixed = claimno[1:-1]
            claimsliststr = claimsliststr.replace(claimno, fixed)
            concatclaim = claimsliststr # Keep track of claim so far incase it is a long claim appearing in multi BR  BR blocks
            if idx <> (len(claimslist)-1): # first, check that there is a next chunk
                if not (re.match('\s{1}\d+\.\s{1,}', claimslist[idx+1][0:10])): # if the next chunk does not have a number, continue
                    continue
        elif re.match('\s{1}\d+\.\s{1}', claimsliststr):
            claimno = re.match('\s{1}\d+\.\s{1}', claimsliststr).group(0)
            fixed = claimno[1:]
            claimsliststr = claimsliststr.replace(claimno, fixed)
            concatclaim = claimsliststr # Keep track of claim so far incase it is a long claim appearing in multi BR  BR blocks
            if idx <> (len(claimslist)-1): # first, check that there is a next chunk
                if not (re.match('\s{1}\d+\.\s{1,}', claimslist[idx+1][0:10])): # if the next chunk does not have a number, continue
                    continue        
        else: # There is not a number in this section! It is an intermediate claim chunk! concatenate with previous claim chunk and check if its the last chunk
            concatclaim += claimsliststr
            #print "Non number chunk found. Concatenated so far is: " + concatclaim
            # First check if we are at the end of the claimslist array - if so, assume it's the last text chunk of this claim and process the claim.
            if idx <> (len(claimslist)-1):  # Then not last claim - look to see if next chunk has a number if so, process the claim. If not, continue.
                if not (re.match('\s{1}\d+\.\s{1,}', claimslist[idx+1][0:10])):
                    continue
                else: # Then multi chunk claim has been processed. reset the claimsliststr to the concatenated claim chunk string
                    claimsliststr = concatclaim
            else: # Then because it is the last element of the claimlist, we are done processing this multi-chunk claim. reset the claimsliststr to the concatenated claim chunk string
                claimsliststr = concatclaim
        # Now get rid of triple spaces
        claimsliststr = claimsliststr.replace("      "," ")
        claimlistfull.append(claimsliststr)
    # Get rid of the _<HR>\n at the end of the last claim:
    claimlistfull[-1] = claimlistfull[-1][:-6]
    patclaimslist = claimlistfull
    # Now get Application claims
    docidapp = pgpubno[3:14]
    #print docidapp
    URL = "http://appft.uspto.gov/netacgi/nph-Parser?Sect1=PTO1&Sect2=HITOFF&d=PG01&p=1&u=%2Fnetahtml%2FPTO%2Fsrchnum.html&r=1&f=G&l=50&s1=%22" + docidapp + "%22.PGNR.&OS=DN/" + docidapp + "&RS=DN/" + docidapp
    page = mech.open(URL)
    html = page.read()
    claimlistfull = []
    claimno =''
    concatclaim = ""
    claimsliststr = ""
    appsplithtml = html.split("<CENTER><B><I>Claims</B></I></CENTER>")
    try:
        split = appsplithtml[1].split("<CENTER><B><I>Description</B></I></CENTER>")
    except IndexError:
        print "Index Error occured for: " + str(docidapp)
        print "AppFT is *mad* - Waiting 30 sec before next query!"
        time.sleep(30)
        page = mech.open(URL)
        html = page.read()
        appsplithtml = html.split("<CENTER><B><I>Claims</B></I></CENTER>")
        split = appsplithtml[1].split("<CENTER><B><I>Description</B></I></CENTER>")
    claimbody = split[0]
    claimslist = claimbody.split("<BR><BR>")[1:]
    for idx,claimstr in enumerate(claimslist):
        # Get rid of \n from end of claim, after the period
        claimstr = re.sub('\.\\n','.',claimstr)
        # Now get rid of all other \n's
        claimsliststr = re.sub('\\n+',' ', claimstr)
        # Now get rid of the space before the claim number - first get the substring with the claim number
        if re.match('\s{1}\d+\.\s{2}', claimsliststr):
            claimno = re.match('\s{1}\d+\.\s{2}', claimsliststr).group(0)
            fixed = claimno[1:-1]
            claimsliststr = claimsliststr.replace(claimno, fixed)
            concatclaim = claimsliststr # Keep track of claim so far incase it is a long claim appearing in multi BR  BR blocks
            if idx <> (len(claimslist)-1): # first, check that there is a next chunk
                if not (re.match('\s{1}\d+\.\s{1,}', claimslist[idx+1][0:10])): # if the next chunk does not have a number, continue
                    continue
        elif re.match('\s{1}\d+\.\s{1}', claimsliststr):
            claimno = re.match('\s{1}\d+\.\s{1}', claimsliststr).group(0)
            fixed = claimno[1:]
            claimsliststr = claimsliststr.replace(claimno, fixed)
            concatclaim = claimsliststr # Keep track of claim so far incase it is a long claim appearing in multi BR  BR blocks
            if idx <> (len(claimslist)-1): # first, check that there is a next chunk
                if not (re.match('\s{1}\d+\.\s{1,}', claimslist[idx+1][0:10])): # if the next chunk does not have a number, continue
                    continue        
        else: # There is not a number in this section! It is an intermediate claim chunk! concatenate with previous claim chunk and check if its the last chunk
            concatclaim += claimsliststr
            #print "Non number chunk found. Concatenated so far is: " + concatclaim
            # First check if we are at the end of the claimslist array - if so, assume it's the last text chunk of this claim and process the claim.
            if idx <> (len(claimslist)-1):  # Then not last claim - look to see if next chunk has a number if so, process the claim. If not, continue.
                if not (re.match('\s{1}\d+\.\s{1,}', claimslist[idx+1][0:10])):
                    continue
                else: # Then multi chunk claim has been processed. reset the claimsliststr to the concatenated claim chunk string
                    claimsliststr = concatclaim
            else: # Then because it is the last element of the claimlist, we are done processing this multi-chunk claim. reset the claimsliststr to the concatenated claim chunk string
                claimsliststr = concatclaim
        # Now get rid of triple spaces
        claimsliststr = claimsliststr.replace("      "," ")
        claimlistfull.append(claimsliststr)
    # Get rid of the _<HR>\n at the end of the last claim:
    claimlistfull[-1] = claimlistfull[-1][:-10]
    appclaimslist = claimlistfull        
    return {'patno': str(patid), 'appno':str(docidapp), 'patclaims':patclaimslist, 'appclaims':appclaimslist}

########## TEST FUNCTION

#retdict = getOnePatAppClaimset("8982981")
#print retdict['patclaims']

#file2writeto = "tricky_patappclaimlist.csv"
# First write the headers to our output file
#with open(file2writeto, 'w') as csvfile:
#	fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
#	writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
#	writer.writeheader()
# Read in each patent from the input file and process for a claimset
#with open("tricky_pats.csv", 'rb') as csvfile:
#    reader = csv.reader(csvfile, delimiter=',')
#    reader.next() # skip header row
#    for row in reader:
#        returnhash = getOnePatAppClaimset(row[0])
#        if returnhash <> 0:
#            # so patent had a pgpub, and both corresponding claimsets were returned
#            # Write out all of the claims row by row into the CSV file
#            patno = returnhash['patno']
#            appno = returnhash['appno']
#            patclaims = returnhash['patclaims']
#            appclaims = returnhash['appclaims']
#            with open(file2writeto, 'a') as csvfile:
#                fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
#                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
#                for claim in patclaims:
#                    writer.writerow({'pat_no': patno, 'app_no':appno, 'pat_claim':claim, 'app_claim':""})
#                for claim in appclaims:
#                    writer.writerow({'pat_no': patno, 'app_no':appno, 'pat_claim':"", 'app_claim':claim})

