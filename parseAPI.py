#! /usr/local/bin/python3.3
# -*- coding: utf-8 -*- 

'''
Created on 1 Aug 2019

@author: U0080217
'''

import requests
from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import Element
import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime
import time 
from datetime import timedelta
from datetime import date 
import os
import shutil
import sys
import urllib
import threading

filings_count = 0
production = False 

'''
#DIRECTORIES -- LOCAL
ftproot = "C:\\Users\\U0080217\\eclipse-workspace\\ElasticSearch\\ElasticSearch\\ftproot\\"
logdirlocal = "C:\\Users\\U0080217\\eclipse-workspace\\ElasticSearch\\ElasticSearch\\logs\\"
mainPath = logdirlocal
pdfdir = "C:\\Users\\U0080217\\eclipse-workspace\\ElasticSearch\\ElasticSearch\\pdf\\"
ingest = "C:\\Users\\U0080217\\eclipse-workspace\\ElasticSearch\\ElasticSearch\\ingest\\"
ownership = "C:\\Users\\U0080217\\eclipse-workspace\\ElasticSearch\\ElasticSearch\\ownership\\"
'''

#DIRECTORIES
ftproot = "/filings/jpfilings/ftproot/"
logdir = "/apps/scripts/solr_upload3/logs/"
logdirqa = "/apps/scripts/logs/"
ingest = "/filings/jpfilings/workbench/ingest/"
ownership = "/filings/jpfilings/sdi-data/ownership/"
pdfdir = "/filings/jpfilings/sdi-data/pdf/"

#start logging
if production == True:
    mainPath = logdir
else:
    mainPath = logdirqa
 
today = date.today()
print(str(today))
logPath = mainPath + "parseAPI_log_" + str(today) + ".txt"
logErrorPath = mainPath + "parseError_log_" + str(today) + ".txt"

with open(logPath,"a") as text_file:
    text_file.write("[" + str(datetime.datetime.now()) + "]" + " Start parseAPI.py" + "\n")

#retrieve the most recent document ingested to SOLR to get date range for API query
if production == True:
    solr_url = "" #provide SOLR URL
else:
    solr_url = "" #provide SOLR URL
    
solr_query = solr_url + "select?q=url%3Asdi-data&rows=1&sort=date%20desc"

try:
    solr_response = requests.get(solr_query)
    solr_response.raise_for_status()
except requests.exceptions.HTTPError as httpE:
    with open(logErrorPath,"a") as text_file:
        text_file.write("[" + str(datetime.datetime.now()) + "] " + str(httpE) + "\n")
    sys.exit(1)
except requests.exceptions.ConnectionError as connectE:
    with open(logErrorPath,"a") as text_file:
        text_file.write("[" + str(datetime.datetime.now()) + "] " + str(connectE) + "\n")
    sys.exit(1)
except Exception as allE:
    with open(logErrorPath,"a") as text_file:
        text_file.write("[" + str(datetime.datetime.now()) + "] " + str(allE) + "\n")
    sys.exit(1)
else:
    f = open("solr_response.xml","wb")
    f.write(solr_response.content)
    f.close()
                
solr_tree = ET.parse("solr_response.xml")
solr_root = solr_tree.getroot()
docid = ""
docdatercvd = ""

for result in solr_root.iter("result"):
    numFound = result.attrib["numFound"]
    if numFound != 0:
        for doc in result:
            for child in doc:
                if child.attrib["name"] == "filings_doc_id":
                    docid = child.text
                if child.attrib["name"] == "tr_rx_date":
                    docdatercvd = child.text
docdatercvd = docdatercvd[:-1]
docdatercvd = datetime.datetime.strptime(docdatercvd, "%Y-%m-%dT%H:%M:%S")
print(docdatercvd)
start = docdatercvd - timedelta(minutes=10)
startstring = start.strftime("%Y-%m-%d") + "T" + start.strftime("%H:%M:%S")
print(startstring)
now = datetime.datetime.utcnow()
nowstring = now.strftime("%Y-%m-%d") + "T" + now.strftime("%H:%M:%S")
print(nowstring)

#log date range for API query
with open(logPath,"a") as text_file:
    text_file.write("[" + str(datetime.datetime.now()) + "]" + " Get date range" + "\n")
    text_file.write("[" + str(datetime.datetime.now()) + "]" + " From " + startstring + " UTC" + "\n")
    text_file.write("[" + str(datetime.datetime.now()) + "]" + " To " + nowstring + " UTC" + "\n")
    
#FUNCTIONS
def getAction(filings_doc_id):
    if production == True:
        action_url = "" #provide SOLR URL
    else:
        action_url = "" #provide SOLR URL
    action_query = action_url + "select?q=filings_doc_id%3A" + filings_doc_id
    action_response = requests.get(action_query)
    f = open("action_response.xml","wb")
    f.write(action_response.content)
    f.close()
    
    action_tree = ET.parse("action_response.xml")
    action_root = action_tree.getroot()
    
    for action_result in action_root.iter("result"):
        action_numFound = action_result.attrib["numFound"]
        if int(action_numFound) > 0:
            return "Overwrite"
        else:
            return "Insert"

def checkDocDate(tr_rx_date,periodEndDate):
    #convert arrive date to JST
    dt_arriveDate = datetime.datetime.strptime(tr_rx_date,"%Y-%m-%dT%H:%M:%S")
    jst_dt_arriveDate = dt_arriveDate + datetime.timedelta(hours=9)
    
    #compare JST arrive date and period end date
    str_jst_arriveDate = jst_dt_arriveDate.strftime("%Y-%m-%dT%H")
    if str_jst_arriveDate == periodEndDate[0:13] or str_jst_arriveDate[0:10] == periodEndDate[0:10]:
        docdate = tr_rx_date
    else:
        docdate = periodEndDate
    return docdate

def getDateDir(basedir,date):
    datestring = time.strptime(date,"%Y-%m-%dT%H:%M:%S")
    year = datestring.tm_year
    month = "{:02d}".format(datestring.tm_mon)
    day = "{:02d}".format(datestring.tm_mday)
    dateDir = basedir + str(year) + "/" + str(month) + "/" + str(day) + "/"
    return dateDir

def writeXML(filings_doc_id,filings_doc_date,tr_rx_date,filings_dcn,formid,form_name,doccategory_id,language,orgid,title,name_en):
    root = Element("env:ContentEnvelope")
    tree = ElementTree(root)
    
    #root attributes
    root.set("xmlns:xsi","http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns","http://filings.schemas.tfn.thomson.com/FilingsDocumentDataItem/2010-07-20/")
    root.set("xmlns:env","http://data.schemas.tfn.thomson.com/Envelope/2008-05-01/")
    root.set("pubStyle","FullRebuild")
    root.set("majVers","3")
    root.set("minVers","0.0")
    
    #header structure
    child_header = Element("env:Header")
    root.append(child_header)
    gchild_info = Element("env:Info")
    child_header.append(gchild_info)
    ggchild_id = Element("env:Id")
    ggchild_timestamp = Element("env:TimeStamp")
    gchild_info.append(ggchild_id)
    gchild_info.append(ggchild_timestamp)
    
    #body structure
    child_body = Element("env:Body")
    root.append(child_body)
    gchild_contentItem = Element("env:ContentItem")
    child_body.append(gchild_contentItem)
    ggchild_data = Element("env:Data")
    gchild_contentItem.append(ggchild_data)
    
    #body attributes
    child_body.set("contentSet","Filings")
    child_body.set("majVers","1")
    child_body.set("minVers","0.0")
    gchild_contentItem.set("action",action)
    ggchild_data.set("xsi:type","Filing")
    
    #actual filings data
    FilingsSubmission = Element("FilingsSubmission")
    ggchild_data.append(FilingsSubmission)
    
    FilingsSubmission.set("xmlns","http://filings.schemas.tfn.thomson.com/FilingsDocument/2010-07-20/")
    
    FilingsSubmissionPermId = Element("FilingsSubmissionPermId")
    FilingsDocId = Element("FilingsDocId")
    FilingsDocumentDate = Element("FilingsDocumentDate")
    FilingsFeedId = Element("FilingsFeedId")
    TRDateReceived = Element("TRDateReceived")
    FilingGeographyId = Element("FilingGeographyId")
    LanguageId = Element("LanguageId")
    FilingsInternalFlag = Element("FilingsInternalFlag")
    FilingsDocumentTitle = Element("FilingsDocumentTitle")
    FilingsRepositoryFileList = Element("FilingsRepositoryFileList")
    FilingsDistributionFileList = Element("FilingsDistributionFileList")
    FilingDocument = Element("FilingDocument")
    FilingsSubmission.append(FilingsSubmissionPermId)
    FilingsSubmission.append(FilingsDocId)
    FilingsSubmission.append(FilingsDocumentDate)
    FilingsSubmission.append(FilingsFeedId)
    FilingsSubmission.append(TRDateReceived)
    FilingsSubmission.append(FilingGeographyId)
    FilingsSubmission.append(LanguageId)
    FilingsSubmission.append(FilingsInternalFlag)
    FilingsSubmission.append(FilingsDocumentTitle)
    FilingsSubmission.append(FilingsRepositoryFileList)
    FilingsSubmission.append(FilingsDistributionFileList)
    FilingsSubmission.append(FilingDocument)
    
    FilingsSubmissionPermId.set("relatedToEntityType","FilingDocument")
    FilingGeographyId.set("effectiveFrom","")
    FilingGeographyId.set("relationType","CountryOfFiling")
    FilingGeographyId.set("relatedToEntityType","Geography")
    LanguageId.set("effectiveFrom","")
    LanguageId.set("relationType","LanguageOfFiling")
    LanguageId.set("relatedToEntityType","Language")
    
    FilingsPrefixPath = Element("FilingsPrefixPath")
    FilingsRepositoryFileList.append(FilingsPrefixPath)
    FilingsDocument = Element("FilingsDocument")
    FilingsPrefixPath.append(FilingsDocument)
    
    FilingsPrefixPath.set("value","")
    
    FilingsDistributionFile = Element("FilingsDistributionFile")
    FilingsDistributionFileList.append(FilingsDistributionFile)
    
    FilerId = Element("FilerId")
    FilingsDmsNumber = Element("FilingsDmsNumber")
    FilingsName = Element("FilingsName")
    FilingsValuesList = Element("FilingsValuesList")
    FilingDocument.append(FilerId)
    FilingDocument.append(FilingsDmsNumber)
    FilingDocument.append(FilingsName)
    FilingDocument.append(FilingsValuesList)
    
    FilerId.set("effectiveFrom","")
    FilerId.set("relationType","FilerOfFiling")
    FilerId.set("relatedToEntityType","Organization")
    
    FilingsSet = Element("FilingsSet")
    FilingsValuesList.append(FilingsSet)
    
    FilingsDcn = Element("FilingsDcn")
    FilingsSubmissionTypeID = Element("FilingsSubmissionTypeID")
    FilingsSubmissionTypeDescription = Element("FilingsSubmissionTypeDescription")
    FilingsDocType = Element("FilingsDocType")
    FilingsCategoryCode = Element("FilingsCategoryCode")
    FilingsSet.append(FilingsDcn)
    FilingsSet.append(FilingsSubmissionTypeID)
    FilingsSet.append(FilingsSubmissionTypeDescription)
    FilingsSet.append(FilingsDocType)
    FilingsSet.append(FilingsCategoryCode)
    
    #content parsed from API
    FilingsDocId.text = filings_doc_id
    FilingsDocumentDate.text = filings_doc_date
    TRDateReceived.text = tr_rx_date
    FilingsDcn.text = filings_dcn
    FilingsType = filings_dcn[:2]
    FilingsSubmissionTypeID.text = formid
    FilingsSubmissionTypeDescription.text = form_name
    FilingsCategoryCode.text = doccategory_id
    LanguageId.text = language
    FilerId.text = orgid
    FilingsDocumentTitle.text = title
    FilingsName.text = name_en
     
    outputDir = ftproot
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")
    xml_output = outputDir + filings_doc_id + ".meta.xml"
    if FilingsType not in ("tn","yo","cr","ib","20","21","22","23","24","25","26","27","28","29"):
        print("Unknown type: " + FilingsType)
        pass 
    elif doccategory_id not in ("1","2","3","7","8","9","12","13","14","15","16","17","18","19","20","21","24","26","30","32","34","37","38","39","41","42","43","44","45","46","47","49","52","53","55","56"):
        print("No JP translation: " + doccategory_id)
        pass 
    elif formid in ("1050","1051","1052","1053","1054","1056","3662","3657"):
        print("No JP translation for Form: " + formid)
        pass
    else:            
        if production == True:
            username = "app2"
        else:
            username = "app2"
        with open(xml_output,"w", encoding="utf-8") as f:
            os.chmod(xml_output, 0o664)
            shutil.chown(xml_output, user=username, group="appuser")
            f.write(xmlstr)

def downloadPDF(filings_doc_id,filings_doc_date,formid):
    pdf_url = "" + filings_doc_id + "&ContentFormat=pdf&ApplicationID=JPF" #provide PDF downloader URL
    pdf_basedir = pdfdir
    pdf_datedir = getDateDir(pdf_basedir, filings_doc_date)
    pdf_file = pdf_datedir + filings_doc_id + ".pdf"
    
    if formid == "963":
        print("Ownership document: do not download PDF.")
        pass
    else:
        if os.path.exists(pdf_file):
            pdf_filesize = os.path.getsize(pdf_file)
            if pdf_filesize <= 1000:
                os.remove(pdf_file)
                urllib.request.urlretrieve(pdf_url,pdf_file)
            else:
                pass
        else:
            if not os.path.exists(pdf_datedir):
                os.makedirs(pdf_datedir)
            urllib.request.urlretrieve(pdf_url,pdf_file)
            os.chmod(pdf_file,0o644)
    moveXML(filings_doc_id, formid,tr_rx_date)

def moveXML(filings_doc_id,formid,tr_rx_date):
    source = ftproot + filings_doc_id + ".meta.xml"
    dest = ingest + filings_doc_id + ".meta.xml"
    
    if os.path.exists(source):
        xml_size = os.path.getsize(source)
        if xml_size > 0:
            if formid == "963":
                own_basedir = ownership
                own_datedir = getDateDir(own_basedir, tr_rx_date)
                destown = own_datedir + filings_doc_id + ".meta.xml"
                if not os.path.exists(own_datedir):
                    os.makedirs(own_datedir)
                try:
                    shutil.move(source,destown)
                except:
                    pass
            else:
                try:
                    shutil.move(source,dest)
                except:
                    pass
     
#retrieve metadata from documents not yet ingested in SOLR
base_query = "" + startstring + "&dateTo=" + nowstring #provide API endpoint
row_query = base_query + "&returnRowCountOnly=true"
getRows = requests.get(row_query)
f = open("getRows.xml","wb")
f.write(getRows.content)
f.close()

getRows_tree = ET.parse("getRows.xml")
getRows_root = getRows_tree.getroot()

for child in getRows_root:
    if "resultSize" in child.tag:
        allRows = child.text
        print(allRows)
        
api_query = base_query + "&rowCount=" + allRows
print(api_query)

try:
    api_response = requests.get(api_query)
    api_response.raise_for_status()
except requests.exceptions.HTTPError as httpE:
    with open(logErrorPath,"a") as text_file:
        text_file.write("[" + str(datetime.datetime.now()) + "] " + str(httpE) + "\n")
    sys.exit(1)
except requests.exceptions.ConnectionError as connectE:
    with open(logErrorPath,"a") as text_file:
        text_file.write("[" + str(datetime.datetime.now()) + "] " + str(connectE) + "\n")
    sys.exit(1)
except Exception as allE:
    with open(logErrorPath,"a") as text_file:
        text_file.write("[" + str(datetime.datetime.now()) + "] " + str(allE) + "\n")
    sys.exit(1)
else:
    f = open("api_response.xml","wb")
    f.write(api_response.content)
    f.close()

api_tree = ET.parse("api_response.xml")
api_root = api_tree.getroot()

for child in api_root:
    if "submissionStatusAndInfo" in child.tag:
        filings_doc_id = child.attrib["commonID"]
        periodEndDate = child[0].attrib["periodEndDate"][0:19]
        tr_rx_date = child[0].attrib["arriveDate"][0:19]
        filings_doc_date = checkDocDate(tr_rx_date, periodEndDate)
        filings_dcn = child[0].attrib["DCN"]
        #formid = child[0].attrib["formType"]
        formType = child[0].attrib["formType"]
        if formType.startswith("0"):
            formid = formType[1:]
        else:
            formid = formType
        form_name = child[0].attrib["formName"]
        doccategory_id = child[0].attrib["categoryID"]
        if child[0].attrib["languageCode"] == "ja":
            language = "505126"
        elif child[0].attrib["languageCode"] == "en":
            language = "505062"
        for gchild in child:
            orgid = gchild[0].attrib["OAPermID"]
            title = gchild[1].text
            for ggchild in gchild:
                if "companyNames" in ggchild.tag:
                    for company in ggchild:
                        name_en = company[0].text
        
        #get action
        action = getAction(filings_doc_id)        
        
        #write to XML
        t1 = threading.Thread(target=writeXML,args=(filings_doc_id, filings_doc_date, tr_rx_date, filings_dcn, formid, form_name, doccategory_id, language, orgid, title, name_en))
        t1.start()
        t1.join()
        #writeXML(filings_doc_id, filings_doc_date, tr_rx_date, filings_dcn, formid, form_name, doccategory_id, language, orgid, title, name_en)
        
        #download PDF
        t2 = threading.Thread(target=downloadPDF,args=(filings_doc_id, filings_doc_date, formid))
        t2.start()
        #downloadPDF(filings_doc_id, filings_doc_date,formid)
        
        with open(logPath,"a") as text_file:
            text_file.write("[" + str(datetime.datetime.now()) + "] " + action + " " + filings_doc_id + ".meta.xml" + "\n")
        filings_count += 1
        
#close log
with open(logPath,"a") as text_file:
    text_file.write("[" + str(datetime.datetime.now()) + "] " + str(filings_count) + " documents processed" + "\n")