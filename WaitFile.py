import webapp2
import jinja2
import xmlrpclib
import os
import logging
import re
import Cookie
import datetime
import email
import calendar
import yaml
import json
from writeGML import write_gml

from google.appengine.api import urlfetch
from google.appengine.api import app_identity
from google.appengine.ext import blobstore

import cloudstorage as gcs

urlfetch.set_default_fetch_deadline(60)


remoteServer = "http://54.214.249.43:9000"
#remoteServer = "http://127.0.0.1:9000"

def convert(input):
    '''
    change array/dict of unicode strings to ascii strings
    '''
    if isinstance(input, dict):
        return dict((convert(key), convert(value)) for key, value in input.iteritems())
    elif isinstance(input, list):
        return [convert(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input


class GAEXMLRPCTransport(object):

    """taken directly from http://brizzled.clapper.org/blog/2008/08/25/making-xmlrpc-calls-from-a-google-app-engine-application/"""
    """Handles an HTTP transaction to an XML-RPC server."""

    def __init__(self):
        pass

    def request(self, host, handler, request_body, verbose=0):
        result = None
        url = 'http://%s%s' % (host, handler)
        try:
            response = urlfetch.fetch(url,
                                      payload=request_body,
                                      method=urlfetch.POST,
                                      headers={'Content-Type': 'text/xml'},
                                      deadline=60)
        except:
            msg = 'Failed to fetch %s' % url
            logging.error(msg)
            raise xmlrpclib.ProtocolError(host + handler, 500, msg, {})

        if response.status_code != 200:
            logging.error('%s returned status code %s' %
                          (url, response.status_code))
            raise xmlrpclib.ProtocolError(host + handler,
                                          response.status_code,
                                          "",
                                          response.headers)
        else:
            result = self.__parse_response(response.content)

        return result

    def __parse_response(self, response_body):
        p, u = xmlrpclib.getparser(use_datetime=False)
        p.feed(response_body)
        return u.close()


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])



def CreateFile(filename, content):
    """Create a GCS file with GCS client lib.

    Args:
    filename: GCS filename.

    Returns:
    The corresponding string blobkey for this GCS file.
    """
    # Create a GCS file with GCS client.
    with gcs.open(filename, 'w') as f:
        f.write(content.encode('utf-8', 'replace'))

    # Blobstore API requires extra /gs to distinguish against blobstore files.
    blobstore_filename = '/gs' + filename
    # This blob_key works with blobstore APIs that do not expect a
    # corresponding BlobInfo in datastore.
    bk = blobstore.create_gs_key(blobstore_filename)
    if not isinstance(bk, blobstore.BlobKey):
        bk = blobstore.BlobKey(bk)
    return bk



class WaitFile(webapp2.RequestHandler):

    """
    manages the waiting between the time a file is sent to the remote server and the time the json is received. prints the status to
    the user (sucess, still watiing, error)
    """

    def compareGenerator(self, moleculeType):
        moleculeNames = []
        for molecule in moleculeType:
            moleculeNames.append(molecule['name'])
        print moleculeNames
        return moleculeNames

    def get_cookie(self, name, default=None):
        """Gets the value of the cookie with the given name,else default."""
        if name in self.request.cookies:
            return self.request.cookies[name]
        return default

    def clear_all_cookies(self):
        """Deletes all the cookies the user sent with this request."""
        for name in self.request.cookies.iterkeys():
            self.clear_cookie(name)

    def clear_cookie(self, name, path="/", domain=None):
        """Deletes the cookie with the given name."""
        expires = datetime.datetime.utcnow() - datetime.timedelta(days=365)
        self.set_cookie(name, value="", path=path, expires=expires,
                        domain=domain)

    def set_cookie(self, name, value, domain=None, expires=None, path="/", expires_days=None):
        """Sets the given cookie name/value with the given options."""

        name = name
        value = value
        if re.search(r"[\x00-\x20]", name + value):   # Don't let us accidentally inject bad stuff
            raise ValueError("Invalid cookie %r:%r" % (name, value))
        new_cookie = Cookie.BaseCookie()
        new_cookie[name] = value
        if domain:
            new_cookie[name]["domain"] = domain
        if expires_days is not None and not expires:
            expires = datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)
        if expires:
            timestamp = calendar.timegm(expires.utctimetuple())
            new_cookie[name]["expires"] = email.utils.formatdate(timestamp, localtime=False, usegmt=True)
        if path:
            new_cookie[name]["path"] = path
        for morsel in new_cookie.values():
            self.response.headers.add_header('Set-Cookie', morsel.OutputString(None))

    def get(self):
        ticket = self.request.get("ticket")
        fileName = self.request.get("fileName")
        fileName2 = self.request.get("fileName2")
        blob1 = self.request.get("blob1")
        blob2 = self.request.get("blob2")
        graphType = self.request.get("graphType")

        resultMethod = self.request.get("resultMethod")
        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        result = s.isready(int(ticket))
        if blob1 not in [None, '']:
            self.set_cookie(name="fileName1", value=fileName)
            self.set_cookie(name="fileName2", value=fileName2)
            self.set_cookie(name="blob1", value=blob1)
            self.set_cookie(name="blob2", value=blob2)
        
        if graphType not in [None, '']:
            self.set_cookie(name="graphType", value=graphType)

        # the first time it loads the page, if the result isnt immediate it will enter this branch
        if result in [-2, '-2']:
            redirectionURL = 'waitFile?ticket={0}&fileName={1}&resultMethod={2}'.format(ticket, fileName, resultMethod)
            template_values = {
                'redirection': redirectionURL,
                'ticket': int(ticket),
                'fileName': fileName,
                'resultMethod': resultMethod
            }
            template = JINJA_ENVIRONMENT.get_template('wait.html')
            self.response.write(template.render(template_values))
        elif result in [-1, '-1']:
            # bad request
            self.response.write("Your request doesn't exist. Please submit your file again")
            return

        else:
            # when the result is here it will enter this branch
            s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
            result = s.getDict(int(ticket))
            if result in ['-5', -5]:
                self.response.write("There was an error processing your request")
                return
            if resultMethod == 'atomize':
                bucket_name = os.environ.get('BUCKET_NAME',
                                             app_identity.get_default_gcs_bucket_name())

                gcs_filename = '/{1}/{0}.bngl'.format(fileName, bucket_name)
                blob_key = CreateFile(gcs_filename, result[0].decode('utf-8', 'replace'))

                log_contents = result[1].decode('utf-8', 'replace')

                # there's some issues in teh atomization process/we know because the log has a non-zero length
                if len(result[1]) > 0:
                    gcs_filename2 = '/{1}/{0}.log'.format(fileName, bucket_name)
                    blob_key2 = CreateFile(gcs_filename2, log_contents)

                    if any([x in log_contents for x in ['ATO1', 'ATO2', 'SCT1', 'SCT2']]):
                        printStatement = '<p><font color="red"> The atomization process is not complete. Please check the atomization log for instructions on what information needs to be verified or provided.</font></p><br/>'
                    else:
                        printStatement = '<p>There are no significant atomization issues, model is ready for use. Please check the log file to review any minor issues that might have surfaced.</p></br>'

                    printStatement += '<a href="/serve/{1}?key={0}">{1}</a><br/>'.format(blob_key, fileName)
                    printStatement += '<a href="/serve/{1}.log?key={0}">{1}.log</a><br/>'.format(blob_key2, fileName)

                else:
                    printStatement = '<a href="/serve/{1}?key={0}">{1}</a><br/>'.format(blob_key, fileName)


                printStatement += 'Visualize: <a href="/graphpredirect?bnglfile={0}&filename={1}">Visualize contact map</a>'.format(blob_key, fileName)
                print 'hello', len(result[1])
                #p2 = output.read()
                self.response.write(printStatement)


            elif resultMethod in ['', 'file']:
                bucket_name = os.environ.get('BUCKET_NAME',
                                             app_identity.get_default_gcs_bucket_name())

                gcs_filename = '/{1}/{0}.bngl'.format(fileName, bucket_name)
                blob_key = CreateFile(gcs_filename, result.decode('utf-8', 'replace'))

                ###
                #blob_info = blobstore.BlobInfo.get(blob_key)
                #output = blob_info.open()
                ###
                printStatement = '<a href="/serve/{1}?key={0}">{1}</a>'.format(blob_key, fileName)
                #p2 = output.read()
                self.response.write(printStatement)
                    # modelSubmission.put()

            elif resultMethod in ['', 'visualize']:
                bucket_name = os.environ.get('BUCKET_NAME',
                                             app_identity.get_default_gcs_bucket_name())

                gcs_filename = '/{1}/{0}.gml'.format(fileName, bucket_name)


                graphType = self.get_cookie('graphType')

                if graphType in ['contactmap', 'regulatory']:
                    blob_key = CreateFile(gcs_filename, result['gmlStr'].decode('utf-8', 'replace'))
                else:
                    blob_key = CreateFile(gcs_filename, result.decode('utf-8', 'replace'))
                ###
                #blob_info = blobstore.BlobInfo.get(blob_key)
                #output = blob_info.open()
                ###

                #self.set_cookie(name="cyjsonGraph", value=result['jsonStr'].decode('utf-8', 'replace'))
                printStatement = '<a href="/serve/{1}?key={0}">{1}</a>'.format(blob_key, fileName)


                #p2 = output.read()
                self.response.write(printStatement)

                if graphType in ['contactmap', 'regulatory']:
                    gcs_filename = '/{1}/{0}.json'.format(fileName, bucket_name)
                    blob_key2 = CreateFile(gcs_filename, result['jsonStr'].decode('utf-8', 'replace'))
                    self.response.write('<br><a href="/visualize?mapType={0}&jsonBlob={1}">Visualize graph online</a>'.format(self.request.get('graphType'), blob_key2))

            elif resultMethod == 'compare':
                #self.set_cookie(name="moleculeType", value=yaml.dump(result))
                moleculeNames1 = self.compareGenerator(result[0])
                moleculeNames2 = self.compareGenerator(result[1])
                fileName1 = self.get_cookie('fileName1')
                fileName2 = self.get_cookie('fileName2')


                template_values = {
                    'fileName1': fileName1,
                    'fileName2': fileName2,
                    'moleculeNames1': moleculeNames1,
                    'moleculeNames2': moleculeNames2
                }
                template = JINJA_ENVIRONMENT.get_template('matchMolecules.html')
                self.response.write(template.render(template_values))

            elif resultMethod == 'normalize':
                fileName1 = self.get_cookie('fileName1')
                fileName2 = self.get_cookie('fileName2')

                bucket_name = os.environ.get('BUCKET_NAME',
                                             app_identity.get_default_gcs_bucket_name())

                gcs_filename = '/{1}/{0}_normalized.bngl'.format(fileName1, bucket_name)
                gcs_filename2 = '/{1}/{0}_normalized.bngl'.format(fileName2, bucket_name)

                blob_key = CreateFile(gcs_filename, result[0][0].decode('utf-8', 'replace'))
                blob_key2 = CreateFile(gcs_filename2, result[0][1].decode('utf-8', 'replace'))

                """
                blob_info = blobstore.BlobInfo.get(blob_key)
                output = blob_info.open()
                """

                self.response.write('Comparison stats:<br>'.format(result[1]['structure'][0], result[1]['structure'][1], fileName1))
                self.response.write('<ul>')
                self.response.write('<li>The models overlap in {0}/{1} of the molecules in {2}</li>'.format(result[1]['structure'][0], result[1]['structure'][1], fileName1))
                self.response.write('<li>The common molecules are {0}</li>'.format(', '.join(result[1]['process'].keys())))
                self.response.write('</ul>')

                self.response.write('Process stats:<br>'.format(result[1]['structure'][0], result[1]['structure'][1], fileName1))
                self.response.write('<ul>')
                self.response.write('<li> Molecules with the same state space<li>')
                self.response.write('<ul>')
                for molecule in result[1]['process'].keys():
                    if 'file1' in result[1]['process'][molecule] and result[1]['process'][molecule]['score'] == 1.0 and result[1]['process'][molecule]['score2'] == 1.0:
                        self.response.write('<li>Molecule {0}\'s state space covers {1} out of {2} possible states'.format(molecule, result[1]['process'][molecule]['file1'],
                                            result[1]['process'][molecule]['totalSpace']))
                self.response.write('</ul>')
                self.response.write('<li> Molecules where {0} contains states {1} does not contain<li>'.format(fileName1, fileName2))
                self.response.write('<ul>')
                for molecule in result[1]['process'].keys():
                    if 'file1' in result[1]['process'][molecule] and result[1]['process'][molecule]['score'] != 1.0:
                        self.response.write('<li>For molecule {0}, the coverage score is {1}/{3}\
     and {2}/{3} for each file. The intersection score is {4}'.format(molecule, result[1]['process'][molecule]['file1'], result[1]['process'][molecule]['file2'],
                                                                      result[1]['process'][molecule]['totalSpace'], result[1]['process'][molecule]['score']))
                self.response.write('</ul>')

                self.response.write('<li> Molecules where {0} contains states {1} does not contain<li>'.format(fileName2, fileName1))
                self.response.write('<ul>')
                for molecule in result[1]['process'].keys():
                    if 'file1' in result[1]['process'][molecule] and result[1]['process'][molecule]['score2'] != 1.0:
                        self.response.write('<li>For molecule {0}, the coverage score is {1}/{3}\
     and {2}/{3} for each file. The intersection score is {4}'.format(molecule, result[1]['process'][molecule]['file1'], result[1]['process'][molecule]['file2'],
                                                                      result[1]['process'][molecule]['totalSpace'], result[1]['process'][molecule]['score2']))
                self.response.write('</ul>')

                self.response.write('</ul><br/>')

                self.response.write('Intersection score is calculated as 1 minus the percentage of states present in {0} not present in {1}'.format(fileName1, fileName2))
                self.response.write('<br><br>Normalized BNGL files:<br>')
                printStatement = '<a href="/serve/{1}_normalized.bngl?key={0}">{1}_normalized.bngl</a><br/>'.format(blob_key, fileName1)
                self.response.write(printStatement)
                printStatement = '<a href="/serve/{1}_normalized.bngl?key={0}">{1}_normalized.bngl</a><br/>'.format(blob_key2, fileName2)

                self.response.write(printStatement)

    def post(self):
        return self.get()


class Visualize(WaitFile):
    '''
    calls cytoscape.js to visualize a contact map
    '''
    def get(self):
        mapType = self.get_cookie('graphType')
        print '---', mapType
        template_values = {}

        if mapType == 'series':
            template_values['data'] = convert(model['timeSeriesJson'])
            template = JINJA_ENVIRONMENT.get_template('/pages/visualizeSeries.html')
            self.response.write(template.render(template_values))
        else:
            modelMap = json.loads(blobstore.fetch_data(self.request.get('jsonBlob'), 0, 900000))
            if mapType == 'contactmap':
                template_values['layout2'] = "{'coolingFactor': 0.95, 'initialTemp': 200,'nodeRepulsion': 100, 'nodeOverlap': 10, 'gravity': 650, 'padding': 4, 'name': 'cose', 'nestingFactor': 2, 'initialTemp ': 2000, 'minTemp': 1, 'numIter': 100, 'edgeElasticity': 500, 'idealEdgeLength': 10}"
                template_values['targetshape'] = "none"
                template_values['typecolor'] = '#fff'
            elif mapType == 'regulatory':
                template_values['targetshape'] = "triangle"
                template_values['layout2'] = "{'name': 'dagre','fit':true,'padding':30,'directed': false}"
                template_values['typecolor'] = '#000'

            template_values['graph'] = convert(modelMap['elements'])
            template_values['layout'] = convert(modelMap['layout'][0])
            template = JINJA_ENVIRONMENT.get_template('visualize.html')
            self.response.write(template.render(template_values))


class ComponentComparison(WaitFile):
    def get(self):
        pass

class Json2gml(webapp2.RequestHandler):
    def post(self):

        cytoscapeJSON = json.loads(self.request.get('cytoscapeJSON'))
        nodeList = []
        edgeList = []
        for node in  cytoscapeJSON['elements']['nodes']:
            nodeInfo = {}

            nodeInfo['data'] = node['data']
            nodeInfo['position'] = node['position']
            nodeList.append(nodeInfo)
            print nodeInfo
        for edge in cytoscapeJSON['elements']['edges']:
            edgeList.append([edge['data']['source'], edge['data']['target']])
            print edge

        graph = {'node': nodeList, 'edge': edgeList}
        gmlString = write_gml(graph)
        print gmlString
        bucket_name = os.environ.get('BUCKET_NAME',
                                     app_identity.get_default_gcs_bucket_name())
        gcs_filename = '/{0}/output.json'.format(bucket_name)
        blob_key = CreateFile(gcs_filename, gmlString)


        printStatement = '<a href="/serve/output.gml?key={0}">download file</a><br/>'.format(blob_key)
        #self.response.headers['Content-Type'] = "text/json"
        #self.response.headers["Content-Disposition"] = 'attachment; filename=output.json'
        #self.response.headers['url'] = "/serve/output.json?key={0}".format(blob_key)

        #self.response.headers.add_header('content-type', 'application/json', charset='utf-8')
        #self.response.out.write(json.dumps({'response':printStatement}))
        self.response.out.write(printStatement)
        print(blob_key)


