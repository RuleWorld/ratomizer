# -*- coding: utf-8 -*-
"""
Created on Wed Jul 17 15:42:26 2013

@author: proto
"""
from __future__ import with_statement

import webapp2
import jinja2
import os
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.api import app_identity

import logging

import xmlrpclib
import urllib
import json
import WaitFile
from collections import defaultdict
import yaml

from google.appengine.api import urlfetch
urlfetch.set_default_fetch_deadline(60)

remoteServer = "http://54.214.249.43:9000"
#remoteServer = "http://127.0.0.1:9000"


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

DATABASE_NAME = 'models'


class ModelInfo(ndb.Model):

    """Models an individual Guestbook entry with author, content, and date."""
    content = ndb.BlobKeyProperty()  # BlobInfo(blobkey)


class MainPage(webapp2.RequestHandler):

    def get(self):
        template_values = {

        }
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


def dbmodel_key(model_name=DATABASE_NAME):
    """Constructs a Datastore key for a ModelDB entity with model_name."""
    return ndb.Key('ModelDB', model_name)



class Translate(webapp2.RequestHandler):

    """
    Class frontend manager for the translate page. Calls the template that the user sees.
    """

    def get(self):
        upload_url = blobstore.create_upload_url('/process')

        #reactionFiles,speciesFiles = s.getSpeciesConventions()
        # print '-----',reactionFiles,speciesFiles
        template_values = {
            'action': upload_url,
            #'reactionDefinition' : ['1','2','3','4','5','6','7','8','9','10','a','b','c']
            #'reactionDefinition' : reactionFiles,
            #'speciesDefinition': speciesFiles
        }
        template = JINJA_ENVIRONMENT.get_template('translate.html')
        self.response.write(template.render(template_values))

class ProcessComparison(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        """
        Process the file comparison form contained in comparison.html. Sends the bngl files to a server
        and returns a list of molecule types to match up. 
        """

        bucket_name = os.environ.get('BUCKET_NAME',
                             app_identity.get_default_gcs_bucket_name())

        upload_files = self.get_uploads('file')
        upload_files2 = self.get_uploads('file2')
        blob_info = upload_files[0]
        reader = blob_info.open()
        bnglContent = reader.read()
        blob_info2 = upload_files2[0]
        reader2 = blob_info2.open()
        bnglContent2 = reader2.read()

        # stores files in the gcs data store for later use.
        element = blob_info.filename
        element2 = blob_info2.filename
        
        gcs_filename = '/{1}/{0}'.format(element, bucket_name)
        blob_key = WaitFile.CreateFile(gcs_filename, bnglContent.decode('utf-8', 'replace'))

        gcs_filename2 = '/{1}/{0}'.format(element2, bucket_name)
        blob_key2 = WaitFile.CreateFile(gcs_filename2, bnglContent2.decode('utf-8', 'replace'))
        


        bnglContent = xmlrpclib.Binary(bnglContent)
        bnglContent2 = xmlrpclib.Binary(bnglContent2)

        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        ticket = s.getMoleculeTypes(bnglContent,bnglContent2)
        # self.response.write(result)

        self.redirect('/waitFile?ticket={0}&fileName={1}&fileName2={2}&blob1={3}&blob2={4}&resultMethod=compare'.format(ticket, element, element2, blob_key, blob_key2))

class ProcessFile(blobstore_handlers.BlobstoreUploadHandler):

    def post(self):
        """
        Process the file translation form contained in translate.html. Calls a remove service defined
        in <remoteServer>, and sends it a file and an atomization flag.
        """
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        reader = blob_info.open()
        sbmlContent = xmlrpclib.Binary(reader.read())
        atomizeString = self.request.get('atomize')
        reaction = self.request.get('reaction')
        species = self.request.get('species')
        # print 'fsdgsdgsd',atomize
        # https://developers.google.com/appengine/docs/python/urlfetch/fetchfunction
        # https://groups.google.com/forum/#!topic/google-appengine/XbrJvt9LfuI
        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        #s = xmlrpclib.ServerProxy('http://127.0.0.1:9000',GAEXMLRPCTransport())
        ticket = s.atomize(sbmlContent, atomizeString, reaction, species)
        # self.response.write(result)

        self.redirect('/waitFile?ticket={0}&fileName={1}.bngl&resultMethod=atomize'.format(ticket, blob_info.filename))


class WaitFileJson(webapp2.RequestHandler):

    def get(self):
        ticket = self.request.get("ticket")
        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        result = s.isready(int(ticket))
        resultJson = {'result': result}
        resultJson = json.dumps(resultJson)
        self.response.headers.add_header('content-type', 'application/json', charset='utf-8')
        self.response.out.write(resultJson)


class generateConfigFile(webapp2.RequestHandler):

    def processPattern(self, pattern):
        # speciesDefinition = re.
        pass

    def get(self):
        names = self.request.get_all("speciesNames")
        patterns = self.request.get_all("patterns")
        results = {'complexDefinition': [], 'reactionDefinition': []}

        for name, pattern in zip(names, patterns):
            processedPattern = self.processPattern(pattern)
            # result.


class Refine(webapp2.RequestHandler):

    def get(self):
        template_values = {

        }
        template = JINJA_ENVIRONMENT.get_template('refine.html')
        self.response.write(template.render(template_values))


class Comparison(webapp2.RequestHandler):

    def get(self):
        upload_url = blobstore.create_upload_url('/processComparison')
        template_values = {
            'action': upload_url,
        }
        template = JINJA_ENVIRONMENT.get_template('compare.html')
        self.response.write(template.render(template_values))


class Normalize(webapp2.RequestHandler):

    def get_cookie(self, name, default=None):
        """Gets the value of the cookie with the given name,else default."""
        if name in self.request.cookies:
            return self.request.cookies[name]
        return default

    def post(self):
        elementDictionary = defaultdict(lambda: defaultdict(str))
        ymlDict = {'model': [{'name': self.get_cookie('fileName1'), 'molecules': []},
                             {'name': self.get_cookie('fileName2'), 'molecules': []}]}

        for element in self.request.POST.items():
            elementDictionary[element[0].split('_')[1]][element[0].split('_')[0]] = element[1]

        fileName1 =  self.get_cookie('fileName1')
        fileName2 =  self.get_cookie('fileName2')
        blob1 =  self.get_cookie('blob1')
        blob2 =  self.get_cookie('blob2')


        for entry in elementDictionary:
            if elementDictionary[entry]['scroll'] != 'None':
                if elementDictionary[entry]['alt'] != '':
                    newName = elementDictionary[entry]['alt']
                else:
                    newName = elementDictionary[entry]['field']
                if newName != elementDictionary[entry]['scroll']:
                    ymlDict['model'][1]['molecules'].append({'name': elementDictionary[entry]['scroll'], 'newname': newName})
            if elementDictionary[entry]['alt'] != '':
                newName = elementDictionary[entry]['alt']
                ymlDict['model'][0]['molecules'].append({'name': elementDictionary[entry]['field'], 'newname': newName})

        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())

        bnglContent1 = xmlrpclib.Binary(blobstore.fetch_data(blob1, 0, 900000))
        bnglContent2 = xmlrpclib.Binary(blobstore.fetch_data(blob2, 0, 900000))
        yamlStr = xmlrpclib.Binary(yaml.dump(ymlDict))

        ticket = s.compareFiles(bnglContent1, bnglContent2, yamlStr)
        # self.response.write(result)

        self.redirect('/waitFile?ticket={0}&resultMethod=normalize'.format(ticket, fileName1))
        
        self.response.write(str(ymlDict))
            


class Graph(webapp2.RequestHandler):

    def get(self):
        upload_url = blobstore.create_upload_url('/graphp')
        #s = xmlrpclib.ServerProxy('http://127.0.0.1:9100')

        template_values = {
            'action': upload_url,
            #'reactionDefinition' : ['1','2','3','4','5','6','7','8','9','10','a','b','c']
        }
        template = JINJA_ENVIRONMENT.get_template('graph.html')
        self.response.write(template.render(template_values))


class ExpandAnnotation(webapp2.RequestHandler):

    def get(self):
        upload_url = blobstore.create_upload_url('/eannotation')
        #s = xmlrpclib.ServerProxy('http://127.0.0.1:9100')

        template_values = {
            'action': upload_url,
            #'reactionDefinition' : ['1','2','3','4','5','6','7','8','9','10','a','b','c']
        }
        template = JINJA_ENVIRONMENT.get_template('annotation.html')
        self.response.write(template.render(template_values))


class ExpandAnnotationMethod(blobstore_handlers.BlobstoreUploadHandler):

    def post(self):

        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        reader = blob_info.open()
        sbmlContent = xmlrpclib.Binary(reader.read())

        # https://developers.google.com/appengine/docs/python/urlfetch/fetchfunction
        # https://groups.google.com/forum/#!topic/google-appengine/XbrJvt9LfuI
        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        #s = xmlrpclib.ServerProxy('http://127.0.0.1:9000',GAEXMLRPCTransport())
        ticket = s.generateAnnotations(sbmlContent)
        # self.response.write(result)

        self.redirect('/waitFile?ticket={0}&fileName={1}'.format(ticket, blob_info.filename))


class GraphFileRedirect(webapp2.RequestHandler):
    def get(self):
        blob_info = self.request.get('bnglfile')
        filename = self.request.get('filename')
        bnglContent = xmlrpclib.Binary(blobstore.fetch_data(blob_info, 0, 900000))
        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        #s = xmlrpclib.ServerProxy('http://127.0.0.1:9000',GAEXMLRPCTransport())
        ticket = s.generateGraph(bnglContent, 'contactmap')
        self.redirect('/waitFile?ticket={0}&fileName={1}_{2}.gml&resultMethod=visualize&graphType={2}'.format(ticket, filename, 'contactmap'))


class GraphFile(blobstore_handlers.BlobstoreUploadHandler):

    def post(self):
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        reader = blob_info.open()
        bnglContent = xmlrpclib.Binary(reader.read())

        returnType = self.request.get('return')
        if returnType == 'Regulatory Graph':
            graphType = 'regulatory'
        elif returnType == 'Contact map':
            graphType = 'contactmap'
        elif returnType == 'SBGN-ER':
            graphType = 'sbgn_er'
        # https://developers.google.com/appengine/docs/python/urlfetch/fetchfunction
        # https://groups.google.com/forum/#!topic/google-appengine/XbrJvt9LfuI
        s = xmlrpclib.ServerProxy(remoteServer, GAEXMLRPCTransport())
        #s = xmlrpclib.ServerProxy('http://127.0.0.1:9000',GAEXMLRPCTransport())
        ticket = s.generateGraph(bnglContent, graphType)
        # self.response.write(result)

        self.redirect('/waitFile?ticket={0}&fileName={1}_{2}.gml&resultMethod=visualize&graphType={2}'.format(ticket, blob_info.filename, graphType))


class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):

    def get(self, resource):
        resource = str(urllib.unquote(self.request.get('key')))
        #blob_info = blobstore.BlobInfo.get(resource)
        self.send_blob(resource)

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/translate', Translate),
    ('/serve/([^/]+)?', ServeHandler),
    ('/process', ProcessFile),
    ('/processComparison', ProcessComparison),
    ('/refine', Refine),
    ('/comparison', Comparison),
    ('/componentComparison', WaitFile.ComponentComparison),
    ('/json2gml',WaitFile.Json2gml),
    ('/visualize', WaitFile.Visualize),
    ('/normalize', Normalize),
    ('/annotation', ExpandAnnotation),
    ('/eannotation', ExpandAnnotationMethod),
    ('/graphpredirect', GraphFileRedirect),
    ('/graphp', GraphFile),
    ('/graph', Graph),
    ('/waitFile', WaitFile.WaitFile),
    ('/testFile', WaitFileJson)
], debug=True)
