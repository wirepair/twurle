#!/usr/bin/env python
import sys
import os
import time
import json
import shutil
import re
import codecs

from threading import Timer
import argparse

import twitter
from twitter import Status

try:
    import requests
except ImportError:
    print "Unable to import requests! Will not be able to gather URLs."

try:
    import lxml.html
except ImportError:
    print "Unable to import lxml! Will not be able to extract titles."

import twurletags

class ExtendedAPI(twitter.Api):
    def GetHomeTimeline(self, count=None, max_id=None, since_id=None):
        parameters = {}

        if since_id:
            parameters['since_id'] = since_id
        if count:
            parameters['count'] = count
        if max_id:
            parameters['max_id'] = max_id
            
        url  = '%s/statuses/home_timeline.json' % self.base_url
        json = self._FetchUrl(url,  parameters=parameters)
        data = self._ParseAndCheckTwitter(json)
        return [Status.NewFromJsonDict(x) for x in data]

class LinkHandler(object):
    
    def extract_type(self, response):
        if 'content-type' in response.headers:
            content = response.headers['content-type']
            if content.startswith('text/html'):
                return 'html'
            elif (content.startswith('image')):
                return 'image'
            elif(content.startswith('application/pdf')):
                return 'pdf'
            elif(content.startswith('application') or
                 content.startswith('audio')):
                return 'data'
        # default to html for now...
        return 'html'
    
    def get_title(self, response):
        content_type = self.extract_type(response)
        charset = self.get_charset(response)
        if content_type == 'html':
            parsed_html = self.parse_body(response)
            if parsed_html is None:
                return None

            title = parsed_html.xpath('//title')
            if (title is not None and len(title) == 1):
                try:
                    return title[0].text_content()                   
                except (UnicodeDecodeError, UnicodeEncodeError), msg:
                    print msg
                    return None
        return None

    def get_charset(self, response):
        from_headers = requests.utils.get_encoding_from_headers(response.headers)
        if from_headers is not None:
            return from_headers
        else:
            from_content = requests.utils.get_encodings_from_content(response.content)
            if (from_content != [] and len(from_content) >= 1):
                return from_content[0]
        return 'utf-8'
            
    def parse_body(self, response):
        try:
            return lxml.html.fromstring(response.content)
        except ValueError, msg:
            print "Error decoding document, returning None"
        return None
    
    def download(self, path, response):
        pass
    
def main():
    parser = argparse.ArgumentParser(
        description='.')
    parser.add_argument('--output_path',
                        '-o',
                        action='store',
                        help='Directory to store twurle output.')
    parser.add_argument('--update_time',
                        '-u',
                        action='store',
                        help='Specifies how often to update URL list in minutes.')
    parser.add_argument('--config_path',
                        '-c',
                        action='store',
                        help='The configuration file to use, default: twurle.config')
    # NOT IMPLEMENTED YET.
    parser.add_argument('--download',
                        '-d',
                        action='store_true',
                        help='Instructs twurle to download non-html files.')
    print "IF YOU PLAN ON GIVING THIS TO PEOPLE OUTSIDE OF VERACODE, PLEASE"
    print "DELETE CONSUMER_KEY AND CONSUMER_SECRET FROM THIS FILE AND "
    print "build_config.py THANK YOU,\nMAINTENCE."
    args = parser.parse_args()
    twurle = TwURLe()
    config_path = args.config_path or 'twurle.config'
    twurle.load(config_path, args)
    twurle.authenticate()
    twurle.start()
    
class TwURLe(object):
    def __init__(self):
        self.last_id = None
        self.config = None
        self.api = None
        self.filelist = None
        self.current_file = time.strftime("%m%d%Y.urls.json", time.localtime())
        self.daily_cache = {}
        self.url_pattern = re.compile("(https?://[^\s]+)")
        self.parser = LinkHandler()
        
    def start(self):
        self._timer()
    
    def _timer(self):
        self.t = Timer(self.config['update_time'], self.run)
        cache_file = time.strftime("%m%d%Y.urls.json", time.localtime())
        print "Cache file: %s"%cache_file
        if self.current_file != cache_file:
            self.daily_cache = {} # empty our cache and make way for new data!
            self.write_filelist(cache_file)
        self.current_file = time.strftime("%m%d%Y.urls.json", time.localtime())
        print "Current file: %s"%self.current_file
        self.t.start()
        
    def write_filelist(self, cache_file):
        if (not os.path.exists(self.config['output_path'])):
            self.check_and_create_path(self.config['output_path'], 'output path')
            
        filepath = self.config['output_path']+os.sep+'filelist.json'
        filelist = []
        try:
            f = open(filepath, 'r')
            filelist = json.load(f)
            f.close()
        except IOError, msg:
            print "File list does not exist, creating!"
        
        try:
            date = time.strftime("%m/%d/%Y", time.localtime())
            # see if the current file is already in the list...
            for filedata in filelist:
                if date in filedata['text']:
                    return
            
            filelist.append({"text": date, "value": cache_file})
            # save the new file.
            f = open(filepath, 'w')
            json.dump(filelist, f, indent=4)
            f.close()
            
        except IOError, msg:
            print "Error saving filelist!"
            return
        
    def load(self, config_path, args):
        """Reads in the config file specified. Some values maybe overridden
        by passing arguments."""
        try:
            print "Loading our configuration file..."
            self.config = json.load(open(config_path, 'r'))
            ret = self._validate_config(args)
            if (ret != 0):
                raise ValueError()
        except IOError, msg:
            print "Unable to open our config file at %s"%config_path
            print "Error msg: ",msg
            sys.exit(-1)
        except ValueError:
            print "Error validating configuration value."
            sys.exit(-2)
            
        self.api = ExtendedAPI()
        self._load_todays_file()
        
    def dump(self):
        """TODO: Be smarter about how we store & dump the tweet data. This *may*
        get large if it holds an entire days worth of tweets with urls..."""
        filepath = self.config['output_path']+os.sep+self.current_file
        try:
            print "Saving tweet data to %s"%filepath
            f = open(filepath, 'w')
            cache = [val for val in self.daily_cache.values()]
            json.dump(cache, f, indent=4)
            f.close()
        except IOError, msg:
            print "Error saving tweet data!"
            print msg
            sys.exit(-5)
    
    def _load_todays_file(self):
        filepath = self.config['output_path']+os.sep+self.current_file
        try:
            f = open(filepath, 'r')
            loaded = json.load(f)
            for tweet in loaded:
                tid = tweet['id']
                if tid > self.last_id:
                    self.last_id = tid
                self.daily_cache[tweet['id']] = tweet
            f.close()
        except ValueError, msg:
            print "Error decoding data, attempting to back it up."
            try:
                shutil.move(filepath, filepath+'.bak')
                print "Moved to %s.bak"%filepath
            except:
                pass
        except IOError, msg:
            # TODO: say stuff
            pass
        
        try:
            cache_file = time.strftime("%m%d%Y.urls.json", time.localtime())
            self.write_filelist(cache_file)
        except Exception, msg:
            print "Error saving filelist!"

    def _validate_config(self, args):
        #override config with supplied arguements.
        try:
            if getattr(args, 'update_time') is not None:
                self.config['update_time'] = args.update_time
        except AttributeError:
            pass
        try:
            if getattr(args, 'output_path') is not None:
                self.config['output_path'] = args.output_path
        except AttributeError:
            pass
        
        
        valid = True
        fields = ['consumer_key','consumer_secret', 'access_token_key',
                  'access_token_secret', 'output_path','update_time']
        for field in fields:
            if field not in self.config or self.config[field] == "":
                print "Error we require the %s field value and it to"\
                " not be empty."%field
                valid = False
        
        if not valid:
            return -1
        
        try:
            self.config['update_time'] = int(self.config['update_time']) * 60
            if self.config['update_time'] == 0:
                print "Update time can not be zero, setting to 1 minute."
                self.config['update_time'] == 60
        except ValueError, msg:
            print "Unable to read update time in minutes, please"\
            " specify a number!"
            return -1
        #self.config['update_time'] = 5
        ret = self.check_output_directories()
        return ret

    def check_output_directories(self):
        if (self.check_and_create_path(self.config['output_path'],
                                       'output path') == -1):
            return -1

        if 'download' not in self.config or self.config['download'] == False:
            return 0

        download_path = self.config['output_path']+os.sep+'downloads'
        if (self.check_and_create_path(download_path, 'download path') == -1):
            return -1
        return 0
        
    def check_and_create_path(self, path, path_type):
        if os.path.exists(path) == False:
            print "Error %s %s does not exist!"%(path_type, path)
            input = raw_input("Shall we attempt to create it? [y/n]: ")
            if (input == 'y'):
                try:
                    os.mkdir(path)
                except IOError, msg:
                    print "Error making %s directory: ",msg
                    return -1
            else:
                print "Invalid %s %s specified."%(path_type, path)
                return -1
        return 0
    
    def authenticate(self):
        if self.api is None:
            print "Unable to access API service."
            sys.exit(-3)
        
        # so dumb, have to give users my dang secrets!
        self.api.SetCredentials(
            consumer_key=self.config['consumer_key'],
            consumer_secret=self.config['consumer_secret'],
            access_token_key=self.config['access_token_key'],
            access_token_secret=self.config['access_token_secret'])
    
        self.user = self.api.VerifyCredentials()
        if (self.user is None):
            print "Unable to authenticate! Please check your"\
            " access token values."
            sys.exit(-4)
        
    def run(self):
        if (self.user is None):
            print "We must authenticate first!"
            sys.exit(-5)
        try:
            self._run()
        except Exception, msg:
            print "Unhandled exception occurred while getting tweets."
            print msg
            import traceback
            traceback.print_exc()
        self._timer()
    
    def _run(self):
        last_id = -1

        try:
            latest_tweet = self.api.GetHomeTimeline(count=1)
            current_id = latest_tweet[0].id
            print "Current tweet id is: %s"%str(current_id)
        except twitter.TwitterError, msg:
            print "Error getting tweets, sleeping until next time..."
            return
        
        while self.last_id <= current_id:
            try:
                tweets = self.api.GetHomeTimeline(count=50, since_id=self.last_id)
            except twitter.TwitterError, msg:
                print "Error getting tweets"
                
            if isinstance(tweets, list) and tweets != []:
                self.last_id = tweets[0].id
                for tweet in tweets:
                    id = tweet.id
                    urls,tags,titles,files = self.extract_real_urls(tweet.text)
                    # no urls, no loggie
                    if urls == []:
                        continue
                    self.daily_cache[id] = {'id': id,
                                            'name': tweet.user.name,
                                            'screen_name': tweet.user.screen_name,
                                            'text': tweet.text,
                                            'url': '<br>'.join(urls),
                                            'tags': '<br>'.join(tags),
                                            'titles': '<br>'.join(titles),
                                            'files': '<br>'.join(files),
                                            'time': tweet.created_at
                    }
                 
            else:
                print "No more tweets."
                break
        self.dump()

    def extract_real_urls(self, text):
        urls = re.findall(self.url_pattern, text)
        if urls == []:
            return [[],[],[],[]]
        titles = []
        tags = []
        files = []
        real_urls = []
        print "Extracted urls: %r"%urls
        if requests is None:
            tags = []
            for url in urls:
                url_text = "<a href=\"%s\">%s</a>"%(url,url)
                real_urls.append(url_text)
                tags.extend(self.get_tags(text, url))
                titles.append('N/A')
                files.append('N/A')
            return [urls,tags,titles,files]
            
        for url in urls:
            print "In url: %s"%url
            # requests follows redirects, because it's Awesome.
            r = None
            try:
                print "Requesting url: %s"%url
                r = requests.get(url)
            except Exception, msg:
                print "Error accessing url %s"%url
                
            if r is not None:
                print "Appending %s"%r.url
                url_text = "<a href=\"%s\">%s</a>"%(r.url,r.url)
                real_urls.append(url_text) # the real (destination) url.
                tag = self.get_tags(text, r.url)
                print "Got tags: %r"%tag
                tags.extend(tag)
                if self.parser is not None:
                    title = self.get_title(r)
                    if title is not None:
                        titles.append(title)
                    else:
                        titles.append('N/A')
                # TODO: Implement file downloading.
                files.append('N/A')
            else:
                # we bombed out of grabbing the url, so make up fake stuff.
                real_urls.append(url)
                tags.extend(self.get_tags(text, url))
                titles.append('N/A')
                files.append('N/A')
        return [real_urls,tags,titles,files]
        
    def get_title(self, response):
        return self.parser.get_title(response)
        
    def get_tags(self, text, url):
        tags = []
        for tag, sites in twurletags.sites.items():
            if tag not in tags:
                for site in sites:
                    if site in url.lower():
                        tags.append(tag)
                        break
        
        for tag, words in twurletags.words.items():
            if tag not in tags:
                for word in words:
                    if word in text.lower():
                        tags.append(tag)
                        break
        return tags
                    
if __name__ == '__main__':
    main()
