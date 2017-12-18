#!/usr/bin/env python
import POSPatentTagger as ptag
#import difflib
#import spacy
# The next import is a script I found on the web that has some functions with SpaCY
#from subject_object_extraction import findSVOs
#from subject_object_extraction import findSubs
#from spacy.symbols import dobj
#import difflib
#from selenium import webdriver
from mechanize import Browser

################################################################################################################
# getIndependentTagged(type,claimlist1,claimlist2)
############################################
# From a specified claim type and given a claim list, extracts the first independent claim of that type of claim
# There are two claim lists given, and ideally the corresponding claim from both list is returned
# as well, an index as to the claim number is returned also for reference to a corresponding untagged claimset later on
# Input types that can be considered: process, machine, manufacture, composition of matter (composition), computer readable medium (crm)
# The claim lists must be POSTagged claim lists. IE the following code would obtain from a patent/pgpub no
# the sets of POSTagges claims necessary for this function as inputs:
# dict = ptag.PatPubClaimEvTag("8724721")
# claimlist1 = dict['PatClaims']
# claimlist2 = dict['AppClaims']
# return values are in the form of a dictionary:
# {"list1claim":claimfromlist1,"list1claimindex":indexofclaimfromlist1,"list2claim":claimfromlist2,"list2claimindex":indexofclaimfromlist2}
################################################################################################################
def getIndependentTagged(type,claimlist1,claimlist2):
    if type == "process":
        flag = 0
        patmethodclaim = []
        appmethodclaim = []
        patmethodclaimno = 0
        appmethodclaimno = 0
        # Get first method/process claim in both        
        for clmindx,claim in enumerate(claimlist1):
            for indx, tag in enumerate(claim):
                # if the current tag lemma is "a" and the subsequent tag lemma is "method" then it should be
                # an independent method claim
                if ((tag[1] == "a") and (claim[indx+1][1] == "method")):
                    patmethodclaim = claim
                    patmethodclaimno = clmindx
                    flag = 1
                    break
                if flag:
                    break
        flag = 0
        for clmindx,claim in enumerate(claimlist2):
            for indx, tag in enumerate(claim):
              # if the current tag lemma is "a" and the subsequent tag lemma is "method" then it should be
              # an independent method claim
                if ((tag[1] == "a") and (claim[indx+1][1] == "method")):
                    appmethodclaim = claim
                    appmethodclaimno = clmindx
                    flag = 1
                    break
                if flag:
                    break
        return {"list1claim":patmethodclaim,"list1claimindex":patmethodclaimno,"list2claim":appmethodclaim,"list2claimindex":appmethodclaimno}
    elif type == "machine":
        print "apparatus claim code here"
    elif type == "manufacture":
        print "manufacture code here"
    elif type == "composition":
        print "composition code here"
    elif type == "crm":
        print "computer readable medium code here"
 
################################################################################################################
# getIndependent(type,claimlist1,claimlist2)
############################################
# From a specified claim type and given a claim list, extracts the first independent claim of that type of claim
# There are two claim lists given, and ideally the corresponding claim from both list is returned
# as well, an index as to the claim number is returned also for reference to a corresponding untagged claimset later on
# Input types that can be considered: process, machine, manufacture, composition of matter (composition), computer readable medium (crm)
# The claim lists are NOT tagged lists. IE the following code would obtain from a patent/pgpub no
# the sets of POSTagges claims necessary for this function as inputs:
# dict = ptag.PatPubClaimEv("8724721")
# claimlist1 = dict['PatClaims']
# claimlist2 = dict['AppClaims']
# return values are in the form of a dictionary:
# {"list1claim":claimfromlist1,"list1claimindex":indexofclaimfromlist1,"list2claim":claimfromlist2,"list2claimindex":indexofclaimfromlist2}
################################################################################################################
def getIndependent(type,claimlist1,claimlist2):
    if type == "process":
        patmethodclaim = ""
        appmethodclaim = ""
        patmethodclaimno = 0
        appmethodclaimno = 0
        # Get first method/process claim in both        
        for clmindx,claim in enumerate(claimlist1):
            if ("method" or "Method") in claim:
                print "got to patclaim"
                patmethodclaim = claim
                patmethodclaimno = clmindx
                break
        for clmindx,claim in enumerate(claimlist2):
            if ("method" or "Method") in claim:
                print "got to app claim"               
                appmethodclaim = claim
                appmethodclaimno = clmindx
                break
        return {"list1claim":patmethodclaim,"list1claimindex":patmethodclaimno,"list2claim":appmethodclaim,"list2claimindex":appmethodclaimno}
    elif type == "machine":
        print "apparatus claim code here"
    elif type == "manufacture":
        print "manufacture code here"
    elif type == "composition":
        print "composition code here"
    elif type == "crm":
        print "computer readable medium code here" 
 
#########################################################################################################################
# rawDifference(claim1,claim2)
##############################
# returns the raw difference using difflib between two claims. Uses sequence matcher on claim strings, and the function
# will tokenize the input claim strings first
# Not sure What I will do with this function - I may remove it because it may not be necessary
#########################################################################################################################
def rawDifference(claim1,claim2):
    # Tokenize the claim strings to create sequences to compare
    nlp = spacy.load('en')
    s1 = nlp.tokenizer(unicode(claim1,'utf_8'))
    s2 = nlp.tokenizer(unicode(claim2,'utf_8'))
    # Here we do the sequence matcher at the character level in the claim strings
    #s = difflib.HtmlDiff(s1,s2)
    tokenrun = ""
    differ = difflib.HtmlDiff()
    html = differ.make_table(s1, s2)
    Html_file= open("diffhtml.html","w")
    Html_file.write(html)
    Html_file.close()
    driver = webdriver.Firefox()
    driver.get("file:///Users/Tim/Documents/BigDataSets/claimevolutionvisualizer/diffhtml.html")
        
        
#########################################################################################################################
# rawDiffViz(claim1,claim2)
##############################
# uses Mechanize to access a webtool using PhP to illustrate claim differences
# Accesses the website www.textdiff.com
# Should set claim1 as the earlier filed claim (like pgpub claim) and claim 2 as the final/patented claim
# Returns HTML formatted (with colors) difference string
#########################################################################################################################
def rawDiffViz(claim1,claim2):
    br = Browser()
    br.set_handle_robots(False)
    br.set_handle_refresh(False)  # can sometimes hang without this
    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]
    br.open("http://www.textdiff.com")
    br.select_form(nr=1)
    br.form["string1"] = claim1
    br.form["string2"] = claim2
    response = br.submit()
    html = response.read()
    # Extract just the htmlwith the color formatted text differences
    colordiff = html.split("<h3>Text Comparison Result &#8211; How the 2nd string was different</h3>")
    split = colordiff[1].split("\n</div>")
    return split[0]


#dict = ptag.PatPubClaimEvTag("8718190")
#patclaims = dict['PatClaims']
#appclaims = dict['AppClaims']
#patclaimsuntagged = dict['PatClaimsUntagged']
#appclaimsuntagged = dict['AppClaimsUntagged']
#idpclaimdict = getIndependent("process",patclaims,appclaims)
#patidpclaim = idpclaimdict["list1claimindex"]
#appidpclaim = idpclaimdict["list2claimindex"]


#print patclaimsuntagged[patidpclaim] +"\n"
#print appclaimsuntagged[appidpclaim]

#htmlret = rawDiffViz(patclaimsuntagged[patidpclaim],appclaimsuntagged[appidpclaim])
#Html_file= open("diffhtml.html","w")
#Html_file.write("<html><body>"+htmlret+"</body></html>")
#Html_file.close()
#driver = webdriver.Firefox()
#driver.get("file:///Users/Tim/Documents/BigDataSets/claimevolutionvisualizer/diffhtml.html")
#idpclaimdict = getIndependent("process",patclaims,appclaims)
#patidpclaim = idpclaimdict["list1claimindex"]
#appidpclaim = idpclaimdict["list2claimindex"]
#print patclaimsuntagged[patidpclaim]+"\n"
#print appclaimsuntagged[appidpclaim]
