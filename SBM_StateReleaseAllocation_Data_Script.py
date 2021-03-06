# Tool to scrape Swachh Bharat Mission data from the sbm.gov.in government website #
# Daniel Robertson                                                                 #
# Petri Autio                                                                      #
# 2016                                                                             #
__author__ = 'petriau'

import ctypes # for popup window
import sys # for exception information

try: # Main exception handler
    
    import requests  # for HTTP requests
    from bs4 import BeautifulSoup  # for HTML parsing
    import bs4  # for type checking
    import xlsxwriter  # for exporting to Excel - need xlsx as over 200k rows of data
    import os  # to find user's desktop path
    import time  # for adding datestamp to file output
    import re  # for regular expressions

    # Timing the script
    startTime = time.time()

    # Configuration of request variables
    url_SBM_FinanceProgress = 'http://sbm.gov.in/sbmreport/Report/Financial/SBM_StateReleaseAllocationincludingUnapproved.aspx'

    # Store data for output
    outputArray = []

    # For finance progress
    componentKey = 'ctl00$ContentPlaceHolder1$ddlComponent'
    componentVal = ''
    finYearKey = 'ctl00$ContentPlaceHolder1$ddlFinYear'
    finYearVal = ''

    # submit button on first page
    submitKey = 'ctl00$ContentPlaceHolder1$btnSubmit'
    submitVal = 'Submit'

    # __EVENTVALIDATION. __VIEWSTATE and __EVENTTARGET are dynamic authentication values which must be freshly updated when making a request.
    eventValKey = '__EVENTVALIDATION'
    eventVal = ''
    viewStateKey = '__VIEWSTATE'
    viewStateVal = ''

    targetKey = '__EVENTTARGET'
    targetVal = ''

    # Function to return HTML parsed with BeautifulSoup from a POST request URL and parameters.
    def parsePOSTResponse(URL, parameters='', pagetype = ''):
        responseHTMLParsed = ''
        attempts = 20
        for i in range(attempts):
            r = requests.post(URL, data=parameters)
            if r.status_code == 200:
                responseHTML = r.content
                responseHTMLParsed = BeautifulSoup(responseHTML, 'html.parser')
            if not responseHTMLParsed == '':
                return responseHTMLParsed
            else:
                print ("    Could not load %s page - attempt %s out of %s" % (pagetype, i+1, attempts))

    # Given two dicts, merge them into a new dict as a shallow copy.
    def merge_two_dicts(x, y):
        z = x.copy()
        z.update(y)
        return z

    # Load the default page and scrape the component, finance year and authentication values
    initPage = parsePOSTResponse(url_SBM_FinanceProgress, 'initial')
    eventVal = initPage.find('input',{'id':'__EVENTVALIDATION'})['value']
    viewStateVal = initPage.find('input',{'id':'__VIEWSTATE'})['value']
    componentOptions = []
    componentOptionVals = []
    componentSelection = initPage.find('select',{'id':'ctl00_ContentPlaceHolder1_ddlComponent'}) #changed for link 2
    componentOptions = componentSelection.findAll('option',{'contents':''}) # changed from selection to contents
    for componentOption in componentOptions:
        componentOptionVal = componentOption['value']
        componentOptionVals.append(componentOptionVal)
    finyearOptions = []
    finYearOptionVals = []
    finYearSelection = initPage.find('select',{'id':'ctl00_ContentPlaceHolder1_ddlFinYear'})
    finYearOptions = finYearSelection.findAll('option',{'contents':''})
    for finYearOption in finYearOptions:
        # Don't include the -2 option which only indicates nothing has been selected in the dropdown
        if not finYearOption['value'] == '-2':
            finYearOptionVal = finYearOption['value']
            finYearOptionVals.append(finYearOptionVal)

    # Initialise workbook
    todaysDate = time.strftime('%d-%m-%Y')
    desktopFile = os.path.expanduser('~/Desktop/SBM_StateReleaseAllocation_' + todaysDate + '.xlsx')
    wb = xlsxwriter.Workbook(desktopFile, {'strings_to_numbers': True})
    ws = wb.add_worksheet('SBM')
    ws.set_column('A:AZ', 22)
    rowCount = 1 # Adjust one row for printing table headers after main loop
    cellCount = 0
    stateCount = 1

    # Global variable to store final table data
    lastTable = ''

    # Global variable for keeping track of the state
    componentCount = 1
    componentName = ''

    # Global variable for ensuring headers get added only once
    headerFlag = False

    # MAIN LOOP: loop through component values. Scrape link values from page
    for componentOptionVal in componentOptionVals: # For testing, we can limit the states processed due to long runtime
        if componentOptionVal == 'C':
            componentName = 'Centre'
        elif componentOptionVal == 'S':
            componentName = 'State'

        eventVal = initPage.find('input',{'id':'__EVENTVALIDATION'})['value']
        viewStateVal = initPage.find('input',{'id':'__VIEWSTATE'})['value']

        # Loop through financial years
        for finYearOptionVal in finYearOptionVals:
            postParams = {
                eventValKey:eventVal,
                viewStateKey:viewStateVal,
                componentKey: componentOptionVal,
                finYearKey: finYearOptionVal,
                submitKey: submitVal
            }


            componentPage = parsePOSTResponse(url_SBM_FinanceProgress, postParams, 'component')

            # Find States
            stateOptions = []
            stateOptionVals = []
            stateSelection = componentPage.findAll('a', {'id': re.compile('stName$')})
            # Find all states and links to click through
            for s in stateSelection:
                stateOptionVal = s.text
                targetOptionVal = s['id']
                stateOptionVals.append([stateOptionVal, targetOptionVal])

            eventVal = componentPage.find('input',{'id':'__EVENTVALIDATION'})['value']
            viewStateVal = componentPage.find('input',{'id':'__VIEWSTATE'})['value']


            # The parameters are quite elaborate needing an entry per link so it's best to put them in a dict
            # Find Links
            linkOptions = []
            linkOptionVals = []
            linkSelection = componentPage.findAll('input', {'id': re.compile('StateId$')})
            for l in linkSelection:
                linkOptions.append([l['name'], l['value']])
            # write links into dictionary to be passed into POST params
            paramDict = {key: str(value) for key, value in linkOptions}

            stateCount = 1
            # Should cycle through all the items in stateOptions
            for s in stateOptionVals:
                stateLinkVal = s[1]
                stateLinkVal = stateLinkVal.replace('_', '$') # Tweaking to get $ signs in the right place
                stateLinkVal = stateLinkVal.replace('rptr$cen', 'rptr_cen') # Tweaking
                stateLinkVal = stateLinkVal.replace('rptr$st', 'rptr_st') # Tweaking!
                stateLinkVal = stateLinkVal.replace('lnkbtn$st', 'lnkbtn_st')

                # Need to call Javascript __doPostBack() on the links
                postParams = {
                    '__EVENTARGUMENT': '',
                    '__EVENTTARGET': stateLinkVal,
                    eventValKey: eventVal,
                    viewStateKey: viewStateVal,
                }
                # Merge with dict of links
                postParams = merge_two_dicts(postParams, paramDict)

                districtPage = parsePOSTResponse(url_SBM_FinanceProgress, postParams, 'component')

                # Process table data and output
                ReportTable = districtPage.find('table')

                # Write table headers
                if not headerFlag:
                    print ('Processing table headers...')
                    headerRows = ReportTable.find('thead').findAll('tr')  # Only process table header data
                    headerTableArray = []
                    rowCount = 0

                    headerStyle = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0A8AD5'})

                    for tr in headerRows[len(headerRows)-1:len(headerRows)]:  # last headeR row only
                        cellCount = 0
                        headerTableRow = []
                        headerCols = tr.findAll('th')
                        # Write state, district, and block headers
                        headerTableRow.append('Component name (State or Centre)')
                        headerTableRow.append('Financial Year')
                        headerTableRow.append('State Name')
                        for td in headerCols:
                            # Tidy the cell content
                            cellText = td.text.replace('\*','')
                            cellText = cellText.strip()
                            # Store the cell data
                            headerTableRow.append(cellText)
                            cellCount = cellCount+1
                        rowCount = rowCount + 1
                        outputArray.append(headerTableRow)

                    headerFlag = True

                # Write table data
                if isinstance(ReportTable,bs4.element.Tag): # Check whether data table successfully found on the page. Some blocks have no data.
                     # Store table for writing headers after loop

                    print ('Currently processing: ' + componentName + ' data for ' + s[0] + ' (' + str(stateCount) + ' of ' + str(len(stateOptionVals)) + ')' + ' for financial year ' + finYearOptionVal)

                    lastReportTable = ReportTable
                    ReportRows = ReportTable.findAll('tr') # Bring entire table including headers because body isn't specified
                    if len(ReportRows) > 4:
                        for tr in ReportRows[4:len(ReportRows)-1]: # Start from 4 (body of table) and total row (bottom of table) dropped
                            cellCount = 0
                            tableRow = []
                            cols = tr.findAll('td')
                            # Write stored information in columns prior to data: Financial Year, State/Center, Statename
                            tableRow.append(componentName)
                            tableRow.append(finYearOptionVal)
                            tableRow.append(s[0])
                            for td in cols:
                                # Tidy and format the cell content
                                cellText = td.text.replace('\*','')
                                cellText = cellText.strip()
                                try:
                                    long(cellText)
                                    cellText = long(cellText)
                                except:
                                    cellText = cellText
                                # Store the cell data
                                tableRow.append(cellText)
                                cellCount = cellCount+1
                            outputArray.append(tableRow)
                            rowCount = rowCount + 1

                    else:
                        sta = "No data recorded for state"
                    stateCount = stateCount + 1
                componentCount = componentCount + 1


    print ('Done processing.' + ' Script executed in ' + str(int(time.time()-startTime)) + ' seconds.')
    # END MAIN LOOP

    # Write output
    r = 0
    for entry in outputArray:
        ws.write_row(r, 0, entry)
        r = r + 1
    # Finally, save the workbook
    wb.close()


except:  # Main exception handler
    try:
        # Write all data into the file
        r = 0
        for entry in outputArray:
            ws.write_row(r, 0, entry)
            r = r + 1

        print("Error occurred, outputted %s rows of data." % r)
        wb.close()
        e = sys.exc_info()
        print(e)
    except:
        print ("Could not output data.")

        print('The program did not complete.')
        e = sys.exc_info()
        print(e)
        ctypes.windll.user32.MessageBoxW(0,
                                         "Sorry, there was a problem running this program.\n\nFor developer reference:\n\n" + str(
                                             e), "The program did not complete :-/", 1)
