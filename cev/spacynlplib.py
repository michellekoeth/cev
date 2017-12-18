#!/usr/bin/env python
# spacynlplib.py - library to process POSTagging and other nlp functions with Spacy
import spacy
import csv
from collections import Counter
import operator

def isLast(itr):
  old = itr.next()
  for new in itr:
    yield False, old
    old = new
  yield True, old

def check_if_claim_is_independent(claimtext,nlp,debug):
    if debug:
        print "Checking for independence for claimtext: " + claimtext
    if ("claim" or "Claim") not in claimtext:
        # Now check if there is a number in the claim - if there is no number, then it's most likely independent
        # use spacy to do this since you may need to further POS examine anyway
        if debug:
            print "There is no claim in claimtext \n"
        doc2 =  nlp(unicode(claimtext,'utf_8'))
        numberlist = [x for x in doc2 if x.tag_ == "CD"]
        if ((len(numberlist) >= 2) or ((len(numberlist) >= 1) and (doc2[0].tag_ == "LS"))): # If there are multiple CD (cardinal nums) or at least one LS & a CD:
            # Lets analyze further for 3-gram of NN-IN-CD
            #print "More than 1 CD found"
            for cd in numberlist:
                if ((cd.head.text == "of") and (cd.head.head.pos_ == "NOUN")): # the second or condition should catch "clam"
                    if debug:
                        print "The claim not indep b/c of head IN or NOUN for CD: " + cd.text
                    return 0
            # no CD in numberlistis an NN-IN-CD arrangement
            if debug:
                print "no CD in numberlist in an NN-IN-CD arragement"
            return 1
        else:
            if debug:
                print "Found ind. claim b/c only one number"
            return 1
    else:
        if debug:
            print "The claim not indep b/c claim in text: " + claimtext
        return 0

###################################################################################################
# matchedclaimset(patclaimset,appclaimset,gowordarr,mistagrulearr,transphrasearr,patnoin,appnoin)
###################################################################################################
# For one patent/pgpub claimset, determine the pgPub claims that match with the issued patent claims
# This is done by creating a "preamble noun signature" - it is presumed (for now) that a patent claim having a same preamble
# noun signature corresponds to a pgpub claim with the same preamble noun signature
# FUNCTION INPUT PARAMETERS:
# patclaimset is a set of patent claims
# appclaimset is the set of claims from the app/pgpub corresponding to the patent
# gowordarr - a training input array that provides keywords specific to a technology that indicate a claim type
# mistagrulearr - a training input array that identifies and corrects words found in a claim likely to be POS mistagged
# transphrasearr - a training input array that identifies phrases that would be used to signal the end of a claim preamble
# patnoin - the patent number for which the provided claimset is being analyzed
# appnoin - the pgpub number for which the provided claimset is being analyzed
# nlp - passed in loaded Spacy corpus - this is so you can run matched_claimset in a loop but only load in
# matchalg2use - specifies what claim matching algorithm to use. Options are:
## "exact_noun_sig" - Use exact order and value of noun signature
# the spaCy english corpus once
##################################################################################################
def matched_claimset(patclaimset,appclaimset,gowordarr,mistagrulearr,transphrasearr,patnoin,appnoin,nlp,matchalg2use):
    # first determine what kind of claim is the claim by the words leading up to the transitional phrase (comprising, consisting essentially of, and consisting of)
    # Consider the first patent claim first as it is the first independent claim
    if patnoin == "0":
        debug = 1
        #print "Patclaimset: " + str(patclaimset)
        #print "Appclaimset: " + str(appclaimset)
    else:
        debug = 0
    transphrase = ""
    type = ""
    patno = patnoin
    appno = appnoin
    preamblegowords = gowordarr
    patpreamblenounsets = []
    apppreamblenounsets = []
    preamblenoun = []
    mistagrules = mistagrulearr
    transphraselist = transphrasearr
    claimpair = []
    phrasefound = 0
    errorfile = "PatentClaimsWithNoProperTransPhrase.csv"
    #fieldnames2 = ['pat_no', 'app_no','pat_claim']
    fieldnames_nomatch = ['pat_no', 'app_no','pat_claim']
    fieldnames_full = ['pat_no','app_no','pat_claim','app_claim']
    match = 0
    indclmcnt = 0
    fullbreak = 0
    # Ideally, replace this with a training file input to populate this set
    statclassset = {"method","apparatus","device","system","circuit"}
    statclasslist = ["method","apparatus","device","system","circuit"]
    # Load in gowords
    # Each row of the file has a keyword,claimtype list
    # For example method, process
    # or device,machine
    # or media,manufacture
    # at least in 375, there are no compositions of matter
    for claim in patclaimset:
        # Check if its an independent claim
        phrasefound = 0
        if debug:
            print "Curr pat claim: " + claim
        retval = check_if_claim_is_independent(claim,nlp,debug)
        if debug: print "retval is: " + str(retval)
        if retval == 1:
            if debug:
                print "This patent claim is independent: " + str(claim)
            indclmcnt += 1
            for phrase in transphraselist:
                if phrase in claim:
                    transphrase = phrase
                    phrasefound = 1
                    break
            if not phrasefound:
                #print "No Transphrase found for claim: " + claim
                # Write out the claim info to the error file
                with open(errorfile, 'a') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames_nomatch)
                    writer.writerow({'pat_no': patno, 'app_no':appno, 'pat_claim':claim})
                continue # Skip this claim since no transphrase was found
            preamble = claim.split(transphrase)[0]
            # so now the preamble string should be everything before the transitional phrase
            # check what words appear in the preamble to determine claim type
            #POSTag the preamble
            doc = nlp(unicode(preamble,'utf_8'))
            for possnoun in doc:
                # Process the  mistagged rules
                for rule in mistagrules:
                    if ((possnoun.lemma_ == rule[0]) and (possnoun.tag_ == rule[1])):
                        preamblenoun.append(possnoun)
                if ((possnoun.pos_ == "NOUN") or (possnoun.pos_ == "PROPN")):
                    preamblenoun.append(possnoun)
            # Now we have all the nouns in the preamble, in the order they appear in the preamble
            # Save this ordered set of preamble nouns for this independent claim, and move to the next independent claim
            patpreamblenounsets.append((claim, preamblenoun))
        # clear out the preamblenoun array for the next claim
        preamblenoun = []
    # Now do the same for the app claims
    for claim in appclaimset:
        # Check if its an independent claim - look at the preamble transphrases
        phrasefound = 0
        if debug:
            print "Curr app claim: " + claim
        if check_if_claim_is_independent(claim,nlp,debug):
            if debug:
                print "This app claim is independent: " + str(claim)
            for phrase in transphraselist:
                if phrase in claim:
                    transphrase = phrase
                    phrasefound = 1
                    break
            if not phrasefound:
                continue
            preamble = claim.split(transphrase)[0]
            # so now the preamble string should be everything before the transitional phrase
            # check what words appear in the preamble to determine claim type
            #POSTag the preamble
            doc = nlp(unicode(preamble,'utf_8'))
            for possnoun in doc:
                # Process the  mistagged rules
                for rule in mistagrules:
                    if ((possnoun.lemma_ == rule[0]) and (possnoun.tag_ == rule[1])):
                        preamblenoun.append(possnoun)
                # must check for proper nouns also so search also on PROPN (for ex, User Element gets tagged as a proper noun)
                if ((possnoun.pos_ == "NOUN") or (possnoun.pos_ == "PROPN")):
                    preamblenoun.append(possnoun)
            # Now we have all the nouns in the preamble, in the order they appear in the preamble
            # Save this ordered set of preamble nouns for this independent claim, and move to the next independent claim
            apppreamblenounsets.append((claim,preamblenoun))
        # clear out the preamblenoun array for the next claim
        preamblenoun = []
    # Now find PatClaim/AppClaim pairing based on signature:
    controllingpatnoun = ""
    for claim in patpreamblenounsets:
        patlemmas = [x.lemma_ for x in claim[1]]
        patnounset = set(patlemmas)
        #if debug:
        #print "Pat noun list: \n" + str(patlemmas)
        matchedclaim = 0
        for appclaim in apppreamblenounsets:
            applemmas = [x.lemma_ for x in appclaim[1]]
            appnounset = set(applemmas)
            #if debug:
            #print "App noun list: \n" + str(applemmas)
            # Noun signatures match - assume it is a corresponding claim
            # match to first match only, then move on to next indp. pat claim
            if matchalg2use == "exact_noun_sig":
                if patlemmas == applemmas:
                    claimpair.append((claim[0],appclaim[0]))
                    # Because this one matched, remove it from potential matching with another independent claim
                    apppreamblenounsets.remove(appclaim)
                    match += 1
                    matchedclaim = 1
                    break
            elif matchalg2use == "no_order_noun_sig":
                if patnounset == appnounset:
                    # Then the two sets match because the difference is the empty set
                    claimpair.append((claim[0],appclaim[0]))
                    match += 1
                    break
            elif matchalg2use == "Exact_List_Then_Others":
                # Match on Exact sig first, if you can:
                if patlemmas == applemmas:
                    claimpair.append(("Matched on exact list: "+ claim[0],appclaim[0]))
                    apppreamblenounsets.remove(appclaim)
                    match += 1
                    matchedclaim = 1 # flags that this patent claim was matched - used to check & record claims that aren't matched
                    break
                # First Match on "statutory class" noun if it is the first, second or third (but try in order) noun in the patent noun list, and if it is the first noun in the app noun list
                for ind,patlem in enumerate(patlemmas):
                    #if set(patlem).issubset(statclassset): # If this is true, the first noun in the patent noun sig is NOT a compound noun
                    if patlem in statclassset: 
                        if len(applemmas) >= (ind +1): # because there may be less app lemma nouns than pat lemma nouns and otherwise you'll get an index error
                            if patlem == applemmas[ind]: # then the same positioned noun in pat matches with the same positioned noun in app
                                # The extra text concatenated on the front of the claim is just for debugging
                                claimpair.append(("Matched on stat class noun: "+patlem+ "The claim is:" + claim[0],appclaim[0]))
                                apppreamblenounsets.remove(appclaim)
                                match += 1
                                matchedclaim = 1 # flags that this patent claim was matched - used to check & record claims that aren't matched
                                fullbreak = 1
                                break
                if fullbreak:
                    fullbreak = 0
                    break
                # Check if pat nounset is superset (has more nouns) than the app noun set. Then, consider if multiple stat types are showing in the claim
                # write out to a file claim matches only this way & see where mismatch happens
                if patnounset.issuperset(appnounset):
                    # The extra text concatenated on the front of the claim is just for debugging
                    claimpair.append(("Matched on the patent nounset being a superset of the app noun set: " + claim[0],appclaim[0]))
                    apppreamblenounsets.remove(appclaim)
                    match += 1
                    matchedclaim = 1 # flags that this patent claim was matched - used to check & record claims that aren't matched
                    # Write out this claim to check for mismatches:
                    with open("Match_by_PatSuperSet_Only_"+matchalg2use+".csv", 'a') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames_full)
                        writer.writerow({'pat_no': patnoin, 'app_no':appnoin, 'pat_claim':claim[0],'app_claim':appclaim[0]})
                    break
                # If no match here, try another match: most frequent reason no match is that the pgpub actually has more nouns in preamble
                # than patent. The controlling noun will be the first noun to appear that is the root of a compound noun, and does not have a "pobj" dependency from a
                # conjunction ("IN") tag. So we'll need to POStag the preamble again and further analyze
                else:
                    for ind,nounobj in enumerate(appclaim[1]): # goes in order - will take controlling nouns in the order presented.1st chek if noun in conjunctive phrase
                        if ((nounobj.dep_ == "pobj") and (nounobj.head.tag_ == "IN")):
                            continue
                        elif ((nounobj.dep_ == "compound") and (nounobj.head.pos_ == "NOUN")):  # Try matching on root of first compound noun
                            controllingpatnoun = ""
                            for patnoun in claim[1]: # Get the head noun and match on this - first find the same noun occurence in the patent preamble This will break after the first compound noun is found.
                                if patnoun.lemma_ == nounobj.lemma_:
                                    controllingpatnoun = patnoun.head.lemma_
                                    break
                                else:
                                    break
                            if nounobj.head.lemma_ == controllingpatnoun:
                                # The extra text concatenated on the front of the claim is just for debugging
                                claimpair.append(("Matched on compound noun match: " +claim[0],appclaim[0]))
                                match += 1
                                matchedclaim = 1
                                apppreamblenounsets.remove(appclaim)
                                with open("Match_by_CompoundNoun_Only_"+matchalg2use+".csv", 'a') as csvfile:
                                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames_full)
                                    writer.writerow({'pat_no': patnoin, 'app_no':appnoin, 'pat_claim':claim[0],'app_claim':appclaim[0]})
                                break
                            # if it doesn't match on the first compound noun to the first patent lemma, then just break
                            else:
                                break
            elif matchalg2use == "pgpub_or_patent_noun_subset_sig":
                patnounset = set(claim[1])
                appnounset = set(appclaim[1])
                if (patnounset.issubset(appnounset) or appnounset.issubset(patnounset)):
                    claimpair.append((claim[0],appclaim[0]))
                    match += 1
                    break
            else:
                print "Matching algorithm requested is not currently supported"
        # You get here when there was no match for the patent noun sig/patent claim. Output it to a file for debugging
        if not matchedclaim:
            unmatchedappclaims = [(x[0],[y.lemma_ for y in x[1]]) for x in apppreamblenounsets]
            with open("No_Matches_"+matchalg2use+".csv", 'a') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames_full)
                writer.writerow({'pat_no': patnoin, 'app_no':appnoin, 'pat_claim':claim[0]+"\n"+str(patlemmas),'app_claim':str(unmatchedappclaims)})
    # Return the pairs of claims
    return {'claimpairs':claimpair, 'matches':match,'numofindependentclaims':indclmcnt}

###################################################################################################
# matchedclaimset_basic(patclaimset,appclaimset)
###################################################################################################
# For one patent/pgpub claimset, determine the pgPub claims that match with the issued patent claims
# This is done by creating a "preamble noun signature" - it is presumed (for now) that a patent claim having a same preamble
# noun signature corresponds to a pgpub claim with the same preamble noun signature
# FUNCTION INPUT PARAMETERS:
# patclaimset is a set of patent claims
# appclaimset is the set of claims from the app/pgpub corresponding to the patent
##################################################################################################
def matched_claimset_basic(patclaimset,appclaimset):
  # since this is intended for a one-off claim match, this function receives a lot less input params and makes more assumptions
  # the transitional phrases checked against shouldn't change much. So in this function, it's static.
  transphrasetuple = ("comprising","comprises","consisting essentially of","consisting of","comprise:","comprised of:","configured to:","operations to:","including:", \
                "to occur:","including","having:","to perform:","performing:","includes:","adapted to:","computer to:","system to:","operable to:","processor to:", \
                "processors to:","device to:","instructions for:","the following instructions:","when executed on a processor:","causes the processor", \
                "causes the computer","cause the processor to","cause a processor to","to cause a computer","to implement:","perform the following:", \
                "performing the following:","perform the following operations","perform the steps of:","to perform the acts of:","to execute the steps of:", \
                "capable of:", "capable of", "characterized by", "obtained by","result in:","characterized in that:","which performs","to:","to execute:", \
                "the actions of:","makes a computer execute a process","wherein:","for causing a computer","having","where","wherein","by:","for:","Table", \
                "being adapted to","being operable to","being arranged to",":")
  # mistag tuple- currently known for electrical
  mistagruletuple = (("mean","VBZ"),("node","RB"),("receiver","RB"),("terminal","JJ"))
  # load in spaCy
  nlp = spacy.load('en')
  # first determine what kind of claim is the claim by the words leading up to the transitional phrase (comprising, consisting essentially of, and consisting of)
  # Consider the first patent claim first as it is the first independent claim
  transphrase = ""
  type = ""
  patpreamblenounsets = []
  apppreamblenounsets = []
  preamblenoun = []
  claimpair = []
  phrasefound = 0
  match = 0
  indclmcnt = 0
  fullbreak = 0
  # Ideally, replace this with a training file input to populate this set
  statclassset = {"method","apparatus","device","system","circuit"}
  statclasslist = ("method","apparatus","device","system","circuit")
  for claim in patclaimset:
    # Check if its an independent claim
    phrasefound = 0
    retval = check_if_claim_is_independent(claim,nlp,0)
    if not retval:
      continue
    indclmcnt += 1
    for phrase in transphrasetuple:
      if phrase in claim:
        transphrase = phrase
        phrasefound = 1
        break
    if not phrasefound:
      continue # Skip this claim since no transphrase was found
    preamble = claim.split(transphrase)[0]
    # so now the preamble string should be everything before the transitional phrase
    # check what words appear in the preamble to determine claim type
    #POSTag the preamble
    doc = nlp(unicode(preamble,'utf_8'))
    for possnoun in doc:
      # Process the  mistagged rules
      for rule in mistagruletuple:
        if ((possnoun.lemma_ == rule[0]) and (possnoun.tag_ == rule[1])):
          preamblenoun.append(possnoun)
      if ((possnoun.pos_ == "NOUN") or (possnoun.pos_ == "PROPN")):
        preamblenoun.append(possnoun)
    # Now we have all the nouns in the preamble, in the order they appear in the preamble
    # Save this ordered set of preamble nouns for this independent claim, and move to the next independent claim
    patpreamblenounsets.append((claim, preamblenoun))
    # clear out the preamblenoun array for the next claim
    preamblenoun = []
    # Now do the same for the app claims
  for claim in appclaimset:
    # Check if its an independent claim - look at the preamble transphrases
    phrasefound = 0
    retval = check_if_claim_is_independent(claim,nlp,0)
    if not retval:
      continue
    for phrase in transphrasetuple:
      if phrase in claim:
        transphrase = phrase
        phrasefound = 1
      break
    if not phrasefound:
      continue
    preamble = claim.split(transphrase)[0]
    # so now the preamble string should be everything before the transitional phrase
    # check what words appear in the preamble to determine claim type
    #POSTag the preamble
    doc = nlp(unicode(preamble,'utf_8'))
    for possnoun in doc:
    # Process the  mistagged rules
      for rule in mistagruletuple:
        if ((possnoun.lemma_ == rule[0]) and (possnoun.tag_ == rule[1])):
          preamblenoun.append(possnoun)
        # must check for proper nouns also so search also on PROPN (for ex, User Element gets tagged as a proper noun)
      if ((possnoun.pos_ == "NOUN") or (possnoun.pos_ == "PROPN")):
        preamblenoun.append(possnoun)
      # Now we have all the nouns in the preamble, in the order they appear in the preamble
      # Save this ordered set of preamble nouns for this independent claim, and move to the next independent claim
    apppreamblenounsets.append((claim,preamblenoun))
    # clear out the preamblenoun array for the next claim
    preamblenoun = []
  # Now find PatClaim/AppClaim pairing based on signature:
  controllingpatnoun = ""
  for claim in patpreamblenounsets:
    patlemmas = [x.lemma_ for x in claim[1]]
    patnounset = set(patlemmas)
    matchedclaim = 0
    for appclaim in apppreamblenounsets:
      applemmas = [x.lemma_ for x in appclaim[1]]
      appnounset = set(applemmas)
      # Match on Exact sig first, if you can:
      if patlemmas == applemmas:
        claimpair.append((claim[0],appclaim[0]))
        apppreamblenounsets.remove(appclaim)
        match += 1
        matchedclaim = 1 # flags that this patent claim was matched - used to check & record claims that aren't matched
        break
      # First Match on "statutory class" noun if it is the first, second or third (but try in order) noun in the patent noun list, and if it is the first noun in the app noun list
      for ind,patlem in enumerate(patlemmas):
        if patlem in statclassset: 
          if len(applemmas) >= (ind +1): # because there may be less app lemma nouns than pat lemma nouns and otherwise you'll get an index error
            if patlem == applemmas[ind]: # then the same positioned noun in pat matches with the same positioned noun in app
              # The extra text concatenated on the front of the claim is just for debugging
              claimpair.append((claim[0],appclaim[0]))
              apppreamblenounsets.remove(appclaim)
              match += 1
              matchedclaim = 1 # flags that this patent claim was matched - used to check & record claims that aren't matched
              fullbreak = 1
              break
      if fullbreak:
        fullbreak = 0
        break
      # Check if pat nounset is superset (has more nouns) than the app noun set. Then, consider if multiple stat types are showing in the claim
      # write out to a file claim matches only this way & see where mismatch happens
        if patnounset.issuperset(appnounset):
          # The extra text concatenated on the front of the claim is just for debugging
          claimpair.append((claim[0],appclaim[0]))
          apppreamblenounsets.remove(appclaim)
          match += 1
          matchedclaim = 1 # flags that this patent claim was matched - used to check & record claims that aren't matched
          # If no match here, try another match: most frequent reason no match is that the pgpub actually has more nouns in preamble
          # than patent. The controlling noun will be the first noun to appear that is the root of a compound noun, and does not have a "pobj" dependency from a
          # conjunction ("IN") tag. So we'll need to POStag the preamble again and further analyze
        else:
          for ind,nounobj in enumerate(appclaim[1]): # goes in order - will take controlling nouns in the order presented.1st chek if noun in conjunctive phrase
            if ((nounobj.dep_ == "pobj") and (nounobj.head.tag_ == "IN")):
              continue
            elif ((nounobj.dep_ == "compound") and (nounobj.head.pos_ == "NOUN")):  # Try matching on root of first compound noun
              controllingpatnoun = ""
            for patnoun in claim[1]: # Get the head noun and match on this - first find the same noun occurence in the patent preamble This will break after the first compound noun is found.
              if patnoun.lemma_ == nounobj.lemma_:
                controllingpatnoun = patnoun.head.lemma_
                break
              else:
                break
            if nounobj.head.lemma_ == controllingpatnoun:
              # The extra text concatenated on the front of the claim is just for debugging
              claimpair.append((claim[0],appclaim[0]))
              match += 1
              matchedclaim = 1
              apppreamblenounsets.remove(appclaim)
              break
            # if it doesn't match on the first compound noun to the first patent lemma, then just break
            else:
              break 
  # Return the pairs of claims
  return {'claimpairs':claimpair, 'matches':match,'numofindependentclaims':indclmcnt}


#############################################################################################
# hotpos(inputfile,pos,nothotwordsfile)
#############################################################################################
# For an input file containing patent/pgpub claimsets of corresponding independent claims,
# (for example the output file from matchedClaimsFromPatAppClaimList)
# determine what of the specified part of speech is changed most often, and the value of those POSes
# the input POS is custom since spaCy makes some quite granular distinctions between just VERB and NOUN, for example
# you may be interested in gerunds (VBG) only which is not a POS in spaCy but a "tag" (more specific).
# For the input purposes of this function though use the following pos input values:
# NOUN = noun, "VBG" = gerund, "ADJ" = adjective
# FUNCTION INPUT PARAMETERS:
# inputfile = output file from matchedClaimsFromPatAppClaimList, which contains patent/pgpub claim pairs
# pos = part of speech to generate "hot list" from, for example: NOUN, VBG or ADJ
# nothotwordsarr = a training array specific to tech so that common POS not directed towards
# inventive concepts are filtered out. This array can be defined by loading in a training file with the necessary info.
# The format of the training file should be word,pos so that one training
# file can be use for any desired pos for a partiular subject matter
#############################################################################################
def hotpos(inputfile,outputfile,pos,nothotwordsarr):
    hotwords = dict()
    poscandidate = None
    patclaimpos = []
    appclaimpos = []
    nothotwords = []
    file2write2 = outputfile
    nlp = spacy.load('en')
    partofspeechtoviz = pos
    with open(inputfile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        # Each row is a patent claim/app claim pair. Row[2] is the patent claim, row[3] is the app claim
        for row in reader:
            # although the file contains patent/app information, we dont need this information since the analysis is as a whole
            # first POS Tag each claim of the corresponding claimset
            patclaimpos = []
            appclaimpos = []
            patclaimpostag = nlp(unicode(row[2],'utf_8'))
            appclaimpostag = nlp(unicode(row[3],'utf_8'))
            # Now determine what nouns are in the patent claim, and what nouns are in the app claim.
            # There is likely to be mistagging. You could also fortify this algorithm by allowing an input
            # mistag training file.
            for posspos in patclaimpostag:
                if pos == "NOUN":
                    if (posspos.pos_ == "NOUN"):
                        if (posspos.lemma_ not in nothotwordsarr):
                            poscandidate = posspos
                        else:
                            continue
                    else:
                        continue
                elif pos == "VBG":
                    if (posspos.tag_ == "VBG"):
                        if (posspos.text not in nothotwordsarr):
                            poscandidate = posspos
                        else:
                            continue
                    else:
                        continue
                elif pos == "ADJ":
                    if (posspos.pos_ == "ADJ"):
                        if (posspos.text not in nothotwordsarr):
                            poscandidate = posspos
                        else:
                            continue
                    else:
                        continue
                else:
                    # this word is not one of the poses we are looking for
                    continue
                # check if the word (which is the lemma attribute of the POS) is already in the list
                # The [item.lemma for item in patclaimpos] should extract the lemma of all poses already entered
                if pos == "NOUN":
                    if poscandidate.lemma_ not in [item.lemma_ for item in patclaimpos]:
                        patclaimpos.append(poscandidate)
                else:
                    if poscandidate.text not in [item.text for item in patclaimpos]:
                        patclaimpos.append(poscandidate)
            # Now get the POSes from the corresponding app claim
            for posspos in appclaimpostag:
                if pos == "NOUN":
                    if (posspos.pos_ == "NOUN"):
                        if (posspos.lemma_ not in nothotwordsarr):
                            poscandidate = posspos
                        else:
                            continue
                    else:
                        continue
                elif pos == "VBG":
                    if (posspos.tag_ == "VBG"):
                        if (posspos.text not in nothotwordsarr):
                            poscandidate = posspos
                        else:
                            continue
                    else:
                        continue
                elif pos == "ADJ":
                    if (posspos.pos_ == "ADJ"):
                        if (posspos.text not in nothotwordsarr):
                            poscandidate = posspos
                        else:
                            continue
                    else:
                        continue
                else:
                    continue
                # check if the word (using the lemma attribute of the POS) is already in the list
                # The [item.lemma for item in patclaimpos] should extract the text of all poses already entered
                # We use the lemma attribute for nouns because it considers the root of the word only so plural = singular
                if pos == "NOUN":
                    if poscandidate.lemma_ not in [item.lemma_ for item in appclaimpos]:
                        appclaimpos.append(poscandidate)
                else:
                    if poscandidate.text not in [item.text for item in appclaimpos]:
                        appclaimpos.append(poscandidate)
            # At this point, we have the set of the specified POS from the patent claim, and the set of POS from the
            # pgpub claim. The sets of POS are unique (i.e. even if a word appears twice, it is only counted once)
            # Now get any of the poses (text value wise) from the patentclaimpos that are not in the appclaimpos
            # we don't need the full spaCy data struct for each word now, although its nice to have if we want to do
            # further proximity analysis. For now, just considering "hotwords" we extract out the values
            if pos == "NOUN":
                patlemmas = [item.lemma_ for item in patclaimpos]
                applemmas = [item.lemma_ for item in appclaimpos]
            else:
                patlemmas = [item.text for item in patclaimpos]
                applemmas = [item.text for item in appclaimpos]
            uniquewordsinclaim = [item for item in patlemmas if item not in applemmas]
            #print uniquewordsinclaim
            # Now we know what pos are uniquely new from the Pgpub to the patent. Integrate the values with whats in there
            # adding a count if that value is already there
            # Our running tally hotwords will be a dictionary, where the word is the key, the count is the value
            newwords = [item for item in uniquewordsinclaim if item not in [key for key in hotwords]]
            existingwords = [item for item in uniquewordsinclaim if item not in newwords]
            for newword in newwords:
                # Add the new word to the hotwords and make the current count 1 (since its the first time we've seen it)
                hotwords[newword] = 1
                #print "Found a new word: " + newword
            for existingword in existingwords:
                hotwords[existingword] += 1
                #print "Hotword now incremented! The hotword is: " + existingword
                #print "The occurence is now: " + str(hotwords[existingword])
    sortedhotwords = sorted(hotwords.items(), key=operator.itemgetter(1), reverse=True)
    # Write to output file
    with open(file2write2, 'wb') as csvfile:
        fieldnames = ['id','value']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        for word in sortedhotwords:
            writer.writerow({'id':word[0],'value':word[1]})
            
###################################################################################################################           
# preambleAnalysis(claimsetfile,stopwordfile,gowordfile,mistagrulefile)
###################################################################################################################
# This function can be used to build the "stopwordfile", "gowordfile" and "mistagrulefile" for training
# preamble noun signature detection. I should rewrite this function to be fully iterative with easier user input
# i.e maybe use a D3 visualization for users to categorize preamble nouns as truly nouns (gowordfile) or
# improperly identified as nouns when really they are either not informative as to the noun signature, or otherwise just
# not acting as a noun (stopwordfile). The mistagrulefile is for correcting noun signature words that are actually nouns and
# should be considered in the analysis, but for some reason tend to be mistagged by Spacy as not being a noun.
# The point of all the training files is so that preamble detection can be made subject matter (Art unit/classification level)
# specific since different "go" and "stop" nouns will be present with different subject matter.
# FUNCTION INPUT PARAMETERS:
# claimsetfile = file of claim sets of the format that the POSPatentTagger.py library can gather/output
# stopwordfile = file with stop words that are not determinative and should be ignored for preamble type/noun signature
# gowordfile = file with words that are determinative for preamble type/noun signature
# mistagrule = file containing translations of commonly mistagged words that are important for preamble type/noun signature
# transphrasefile = file containing transitional phrases used to signify the end of the claim preamble
# you can develop your training models by starting out with very thin or basic training files, and studying the
# printed results to see how the training models should be completed for a particular subject matter
##################################################################################################################
def preambleAnalysis(claimsetfile,stopwordfile,gowordfile,mistagrulefile,transphrasefile):
    # Given a set of claims from a specified filename, what is the most prevelant "claim type" words that appear in the preamble?
    transphrase = ""
    type = ""
    preamble = ""
    bagofpreambles = ""
    preamblenouns = []
    nlp = spacy.load('en')
    preamblestopwords = []
    preamblegowords = []
    mistagrules = []
    transphrasearr = []
    patno = ""
    phrasefound = 0
    typedict = {"Process":0, "Machine":0, "Manufacture":0, "Composition of Matter":0}
    # Load in stopword file for preambles
    with open(stopwordfile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            preamblestopwords.append(row[0])
    # Load in goword
    # Each row of the file has a keyword,claimtype list
    # For example method, process
    # or device,machine
    # or media,manufacture
    # or composition of matter
    with open(gowordfile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            preamblegowords.append((row[0],row[1]))
    # Load in mistag rules
    with open(mistagrulefile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            mistagrules.append((row[0], row[1]))
    # Load in transphrases
    with open(transphrasefile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            transphrasearr.append(row[0])
    # Now load in and analyze the claimset
    with open(claimsetfile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            # First process the independent claims from the patent claimsets (without distinguishing between patents)
            # Skip dependent claims - assume the word claim appears in a dep. claim
            patno = row[0]
            if ((row[2] <> "") and ("claim" not in row[2])):
                claim = row[2]
                for phrase in transphrasearr:
                    if phrase in claim:
                        transphrase = phrase
                        phrasefound = 1
                        break
                if phrasefound:
                    preamble = claim.split(transphrase)[0]
                    # Now lets tag the preamble to extract out the noun
                    doc = nlp(unicode(preamble,'utf_8'))
                    preamblenoun = []
                    for possnoun in doc:
                        # Get all the nouns in this preamble, go in order of appearence. Assuming nouns are determinative of claim type
                        if (possnoun.pos_ == "NOUN"):
                            if possnoun.lemma_ not in preamblestopwords:
                                preamblenoun.append(possnoun.lemma_)
                        # Process the  mistagged rules
                        for rule in mistagrules:
                            if ((possnoun.lemma_ == rule[0]) and (possnoun.tag_ == rule[1])):
                                preamblenoun.append(possnoun.lemma_)

                    # Now categorize the main preamble noun type (i.e. apparatus, method)
                    phrasefound = 0
                    # this goes in order of the preamblegowords, the training file should
                    # list the gowords in order of priority (i.e. method and apparatus above more specific terms)
                    # Thus, the claim gets classified by the broader type noun first in case the preamble has mixed noun type words
                    # (i.e. A method for an equalizer - would return "method" instead of "equalizer")
                    for preamblegoword in preamblegowords:
                        if preamblegoword[0] in preamblenoun:
                            preamblenouns.append(preamblegoword[0])
                            # Increment the type of claim found by one (preamblegoword[1] will be the key into the dict for the tally)
                            typedict[preamblegoword[1]] += 1
                            phrasefound = 1
                            break
                    # This if is true if none of the preamblegowords are found in the preamble
                    # These preambles should be few in number - they represent ambiguities or even ineligible subject matter
                    # I may want to simply disregard these patents or claims in my claim analysis
                    if not phrasefound:
                        print "Patent No: " + str(patno) + " Had the following outlier preamble (either transitional phrase could not be found or the claim type could not be determined): " + str(doc)
    # Now tally the most popular preamble nouns - this will inform
    preamblenoundict = Counter(preamblenouns)
    print preamblenoundict
    print typedict

    
####################################################################################################################
# matched_claims_from_pat_app_claimlist(inputfile,outputfile,preamblgowordsarr,mistaggedrules,transphrasearr)
####################################################################################################################
# For a given input file of patent nos, corresponding app nos, and their respective claimsets
# (A working input file would be an aggregate output of the POSTPatentTagger.py getOnePatAppClaimset(patid) function,
# Where such an aggregate output file is generated via the createClaimsFile function from the cevcontroller_flask.py
# this function being invoked by the Claim Extraction self-service function of the CEV website)
# FUNCTION INPUT PARAMETERS:
# inputfile: Claimset file aggregate from the output of POSTPatentTagger.py getOnePatAppClaimset(patid) function
# outputfile: Where to write the matched claimset output to
# preamblegowordsarr: an input array of the preamble "go" words
# mistaggedrules: an input array of rules that define how to fix mistagged words
# transphrasearr: an input array of transitional phrases to consider in determining where preambles end
# matchalgtype: A string identifier saying which claim matching algorithm to use. The following options are available:
### "exact_noun_sig": Use the exact noun signature (order + value of nouns in preamble must match exactly)
#(OPTIONAL ADDITIONAL ARG *args) : an optional arg is the celery job. This is so this function can pass in status updates
# if it is run as a background job with celery.
##############################################################################################################
def matched_claims_from_pat_app_claimlist(inputfile,outputfile,preamblgowordsfn,mistaggedrulesfn,transphrasefn,matchalgtype,*args):
    patno = 0
    appno = 0
    # index is used to reduce dataset to toyset for now
    index = 0
    # readind is for celery status updates
    readind = 0
    # counter for when claims dont match
    nomatch = 0
    # counter for when match does happen
    match = 0
    # Running tally of found independent claims and matches for algorithmic accuracy purposes
    num_of_matches = 0 
    num_of_independent_claims = 0
    fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
    fieldnames_nomatch = ['pat_no', 'app_no','pat_claim']
    #max = 30
    patclaimset = []
    appclaimset = []
    file2writeto = outputfile
    claimsetfile = inputfile
    nlp = spacy.load('en')
    if args:
        celeryjob = args
        celeryjob.update_state(state="PROGRESS", meta={'current':0, 'total':0, 'status':"About to Load in Training files"})
    # array to store the transphrases:
    transphrasearr = []
    # array to store the gowords:
    gowordarr = []
    # array to store the mistagrules:
    mistagrulesarr = []
    # Load in training files
    with open(transphrasefn, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            transphrasearr.append(row[0])
    with open(preamblgowordsfn, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            gowordarr.append((row[0],row[1]))
    # Load in mistag rules
    with open(mistaggedrulesfn, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            mistagrulesarr.append((row[0], row[1]))
    # Write headers for output file
    with open(file2writeto, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
    with open("No_Matches_" + matchalgtype+".csv", 'wb') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames_nomatch)
        writer.writeheader()
    totallines = len(open(claimsetfile).readlines())
    if args:
        celeryjob.update_state(state="PROGRESS", meta={'current':0, 'total':totallines, 'status':"Training files Loaded - starting claimset matching processing"})
    with open(claimsetfile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for line_num, (is_last,row) in enumerate(isLast(reader)):
            # limit reading in only max number of patents to process for testing #unconmment for test purposes only
            #if index > max:
            # break 
            # Find the independent patent claims
            readind += 1
            if args:
                celeryjob.update_state(state="PROGRESS", meta={'current':readind, 'total':totallines, 'status':"Matching Claimsets"})
            if patno == 0:
                patno = row[0]
                appno = row[1]
            if ((row[0] <> patno) or (is_last)):
                # Then a new patent is loaded in now. Process the current claimsets
                # matched_claimset should be claim matching scheme 1 - strict sequence and value noun signature
                retdict = matched_claimset(patclaimset,appclaimset,gowordarr,mistagrulesarr,transphrasearr,patno,appno,nlp,matchalgtype)
                retarray = retdict['claimpairs']
                # Keep track of independent claims processed and matches found:
                num_of_matches += retdict['matches']
                num_of_independent_claims += retdict['numofindependentclaims']    
                # Write out the matched claimsets to a file
                with open(file2writeto, 'a') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    for claim in retarray:
                        writer.writerow({'pat_no': patno, 'app_no':appno, 'pat_claim':claim[0], 'app_claim':claim[1]})
                patclaimset = []
                appclaimset = []
                patno = row[0]
                appno = row[1]
                index += 1
            # Get the patent indepndent claimset - assumes that any claim without the word "claim" in it is an independent claim
            if ((row[2] <> "") and ("claim" not in row[2])):
                patclaimset.append(row[2])
            # Get the application independent claimset
            if ((row[3] <> "") and ("claim" not in row[3])):
                appclaimset.append(row[3])
    # The input patent/pgpub claims has now been fully analyzed. Return the count statistics:
    return {'num_of_matches':num_of_matches,'num_of_independent_claims':num_of_independent_claims}
                
 # Generates a test corpus from a bigger set
def generate_test_claimset_corpus(inputfile,outputfile,numofpatents):
    start = 0
    max = numofpatents
    patno = ""
    fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
    with open(outputfile, 'wb') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
    with open(inputfile, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            if patno <> row[0]:
                patno = row[0]
                start += 1
            with open(outputfile, 'a') as csvfile2:
                writer = csv.DictWriter(csvfile2, fieldnames=fieldnames)
                writer.writerow({'pat_no':row[0], 'app_no':row[1], 'pat_claim':row[2], 'app_claim':row[3]})
            if start == max:
                break

def generate_output_matchfile_differences(inputfilelarger,inputfilesmaller,outputfile):
    largematchdata = []
    smallermatchdata = []
    with open(inputfilelarger, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            largematchdata.append((row[0],row[1],row[2],row[3]))
    with open(inputfilesmaller, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        reader.next() # skip header row
        for row in reader:
            smallermatchdata.append((row[0],row[1],row[2],row[3]))
    s = set(smallermatchdata)
    difflist = [x for x in largematchdata if x not in s]
    #print difflist
    fieldnames = ['pat_no', 'app_no','pat_claim','app_claim']
    with open(outputfile, 'wb') as csvfile2:
        writer = csv.DictWriter(csvfile2, fieldnames=fieldnames)
        writer.writeheader()
        for item in difflist:
            writer.writerow({'pat_no':item[0], 'app_no':item[1], 'pat_claim':item[2], 'app_claim':item[3]})
            
#hotpos("patappmatchedclaimsets_Test.csv","hotADJs_2630_FullPart1.csv","ADJ",nothotwordsarr)

# To be more operationally efficient, load in all the stop/go/nothot/rules files into arrays and pass the arrays instead of the filenames

# nothotwords
#nothotwordsarr = []

# Load in the not hot words:
# Change posmain to be whatever part of speech you want to load in
#posmain = "NOUN"
#with open("nothotwords2630.csv", 'rb') as csvfile:
#    reader = csv.reader(csvfile, delimiter=',')
 #   reader.next() # skip header row
 #   for row in reader:
 #       if row[1] == posmain:
 #           nothotwordsarr.append(row[0])

#generate_test_claimset_corpus("patappclaimlist375_No240_Part1.csv","patappclaimlist_Test_10_23_10000Patents.csv",10000)
#claimmatchalg2use = "exact_noun_sig"
#claimmatchalg2use = "no_order_noun_sig"
#claimmatchalg2use = "at_least_pgpub_noun_set_sig"
#claimmatchalg2use = "pgpub_or_patent_noun_subset_sig"
#claimmatchalg2use = "Exact_List_Then_Others"
#retdict2 = matched_claims_from_pat_app_claimlist("patappclaimlist_new_test_10_27.csv","patappmatchedclaimsets_test_10_27_New.csv","preamblegowords2630.csv","mistagrules2630.csv","transphrases2630.csv",claimmatchalg2use)
#print "Claim Match Algorithm used: " + claimmatchalg2use
#print "Total number of independent patent claims evaluated: " + str(retdict2['num_of_independent_claims'])
#print "Number of matches of independent patent claims: " + str(retdict2['num_of_matches'])
#print "Number of independent patent claims for which matches were not found: " + (str(retdict2['num_of_independent_claims'] - retdict2['num_of_matches']))


#generate_output_matchfile_differences("tricky_patappclaimlist.csv","patappmatchedclaimsets_tricky.csv","Diff_Any_Superset_vs_PatentOnlySuperset.csv")