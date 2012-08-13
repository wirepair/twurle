requirements: 
You should install (using pip or setuptools in python):
requests: pip install requests
lxml: pip install lxml
python-twitter: pip install python-twitter


configuration:
Once those are installed, go to https://dev.twitter.com, create a new application and copy the consumer_key and consumer_secret to the build_config.py file.
Then simply run:
python build_config.py
or 
build_config.py (in windows)

The config program will give you a URL to visit, and give you a pin code.
Type the pincode into the terminal. If all goes well you'll see your key/token.
Next tell twurle where to save the data to. This should be /%path where twurle.py is%/output if you want the HTML to load the json properly without having to modify it. 

You do NOT need a webserver, if you use Firefox or IE, you can load the data from local disk. Only google chrome requires you to run a web server.