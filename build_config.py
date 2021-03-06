#!/usr/bin/env python

# Copyright 2007 The Python-Twitter Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import sys

# parse_qsl moved to urlparse module in v2.6
try:
  from urlparse import parse_qsl
except:
  from cgi import parse_qsl

import json

import oauth2 as oauth

REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
ACCESS_TOKEN_URL  = 'https://api.twitter.com/oauth/access_token'
AUTHORIZATION_URL = 'https://api.twitter.com/oauth/authorize'
SIGNIN_URL        = 'https://api.twitter.com/oauth/authenticate'

# go to http://dev.twitter.com to create a new app and add the values here!
consumer_key    = ''
consumer_secret = ''
if consumer_key == '' or consumer_secret == '':
  print "You must create a new app from https://dev.twitter.com and add the consumer key/secret.'
  exit()
  
config['consumer_key'] = consumer_key
config['consumer_secret'] = consumer_secret
signature_method_hmac_sha1 = oauth.SignatureMethod_HMAC_SHA1()
oauth_consumer             = oauth.Consumer(key=consumer_key, secret=consumer_secret)
oauth_client               = oauth.Client(oauth_consumer)
config = {}

get_token = raw_input("Would you like to attempt to retrieve access tokens? [y/n]: ")
if get_token == 'y':        
    print 'Requesting temp token from Twitter'
    resp, content = oauth_client.request(REQUEST_TOKEN_URL, 'GET')
    if resp['status'] != '200':
        print 'Invalid respond from Twitter requesting temp token: %s' % resp['status']
    else:
        request_token = dict(parse_qsl(content))
        print ''
        print 'Please visit this Twitter page and retrieve the pincode to be used'
        print 'in the next step to obtaining an Authentication Token:'
        print ''
        print '%s?oauth_token=%s' % (AUTHORIZATION_URL, request_token['oauth_token'])
        print ''
        
        pincode = raw_input('Pincode? ')
        
        token = oauth.Token(request_token['oauth_token'], request_token['oauth_token_secret'])
        token.set_verifier(pincode)
        
        print ''
        print 'Generating and signing request for an access token'
        print ''
        
        oauth_client  = oauth.Client(oauth_consumer, token)
        resp, content = oauth_client.request(ACCESS_TOKEN_URL, method='POST', body='oauth_verifier=%s' % pincode)
        access_token  = dict(parse_qsl(content))

    if resp['status'] != '200':
        print 'The request for a Token did not succeed: %s' % resp['status']
        print access_token
    else:
        print 'Your Twitter Access Token key: %s' % access_token['oauth_token']
        print '          Access Token secret: %s' % access_token['oauth_token_secret']
        print ''
    
    config['access_token_key'] = access_token['oauth_token']
    config['access_token_secret'] = access_token['oauth_token_secret']
else:
    config['access_token_key'] = raw_input('Please enter your access token key: ')
    config['access_token_secret'] = raw_input('Please enter your access token secret: ')

config['output_path'] = raw_input('Please enter the path where you wish to save the results: ')
config['update_time'] = raw_input('Enter time in minutes you wish to check for updates: ')

#TODO: Implement, maybe.
"""
config['download'] = raw_input('Would you like to download files that are linked? [y/n]: ')
if config['download'] == 'y':
    config['download'] = True
else:
    config['download'] = False
"""

try:
    json.dump(config, open('twurle.config','w'), indent=4)
    print "Configuration saved successfully."
except Exception, msg:
    print "Error saving twurle configuration, verify you have proper permissions"
    print "Error: ",msg
