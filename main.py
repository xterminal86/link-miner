#!/usr/bin/python3

import sys;
import logging;
import threading;
import time;
import re;
import requests;
import signal;
import argparse;

from threading import Lock;

ThreadLock = Lock();

# Initial URL to mine from
Start = {};

# Result will be stored here
Urls = {};

ExitApp = False;
StopWriting = False;
NoMeta = True;
HttpOnly = True;

# Worker threads
MaxThreads = 1;

# Maximum number of requests
MaxIterations = 10;

# Requests counter
Iterations = 0;

# Number of seconds to sleep after thread work is done
SleepSeconds = 1;

# Flag that determines if results have already been written to file
ResultsWritten = False;

# Timeout for request.get()
TimeoutSeconds = 5;

# Verbose flag sets this to logging.INFO
LogLevel = logging.CRITICAL;

def FindUrls(string):
  global HttpOnly;
  
  # findall() has been used
  # with valid conditions for urls in string
  str = string.decode("iso-8859-1");

  urls = "";
  
  if HttpOnly == True:
    urls = re.findall('http://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', str);
  else:
    urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', str);
    
  return urls;

def GetMetadata(content):
  retVal = "<NONE OR COULDN'T GET>";
  str = content.decode("utf-8");
  lowercase = str.lower();
  r = lowercase.find('<meta name="description" content=');
  rest = lowercase[r:];
  res = rest.find('>');
  if res != -1:
    s = str[r:];
    retVal = s[:res + 1];
  else:
    res = rest.find('/>');
    if res != -1:
      s = str[r:];
      retVal = s[:res];
  #print("{0}\n>>>\n{1}\n<<<\n\n".format(res, retVal));
  return retVal;

# Returns URL without trailing part
# (i.e. http://test.com not http://test.com/fuck/bees?id=42)
def GetBaseUrl(url):
  baseUrl = "";
  stopChars = [ '?', '&', '\'', '"', '\n', ' ', ':' ];
  slashCount = 0;
  for c in url:
    if c == '/':
      slashCount += 1;
      if slashCount == 3:
        break;

    # If we encountered something like
    # http://fuck.bees?sumShiet=33 or http://fuck.bees&sumShiet=33
    if slashCount == 2 and (c in stopChars):
      break;

    baseUrl += c;
  return baseUrl;

def WriteResults():
  global ResultsWritten;
  global TimeoutSeconds;
  global StopWriting;
  global NoMeta;
  
  if ResultsWritten == True:
    return;
    
  print("Writing results ({0} links mined)...".format(len(Urls)));
  f = open("links.txt", "w", encoding="utf-8");
  counter = 0;
  total = len(Urls);
  for key in Urls:    
  
    if StopWriting == True:
      break;    
    
    meta = Urls[key];
    
    if NoMeta == False:
      try:
        r = requests.get(key, timeout=TimeoutSeconds);
        meta = GetMetadata(r.content);
      except:
        continue;
      
    try:
      f.write("{0}\n>>>\n{1}\n<<<\n\n".format(key, meta));
    except:
      f.write("{0}\n>>>\n{1}\n<<<\n\n".format(key, sys.exc_info()));
      continue;
      
    print(" Writing {0}/{1}\r".format(counter + 1, total), end="");    
    counter += 1;    
    
  f.close();
  print("\nDone!");
  ResultsWritten = True;

def thread_function(name):
  global ExitApp;
  global Iterations;
  global MaxIterations;
  global TimeoutSeconds;
  global SleepSeconds;
  global MaxThreads;
  
  progr = [ '|', '/', '-', '\\' ];
  maxRetries = 3;
  retryCount = 0;
  
  logging.info("Thread %s: starting", name)

  while True:
    if ExitApp == True or retryCount > maxRetries:
      break;
    
    urlForRequest = "";

    if Iterations > MaxIterations:
      ThreadLock.acquire();
      ExitApp = True;
      ThreadLock.release();
      break;

    if len(Start) != 0:
      ThreadLock.acquire();
      key = list(Start.keys())[0];
      urlForRequest = key;
      Start.pop(key);
      ThreadLock.release();
      retryCount = 0;
    else:          
      if MaxThreads > 1:        
        logging.info("Thread {0} - no jobs (try {1}/{2})".format(name, retryCount, maxRetries));
        
        # Since this shit is kinda multithreaded, there can be a situation
        # when dictionary of links yet to be processed is empty,
        # because other thread(s) has emptied it.
        # So we can't just abort thread on condition if dictionary is empty,
        # because it may result in the whole process to be degenerated 
        # into single threaded type because, e.g., first thread have just popped
        # starting item and all others now see that dictionary as empty. 
        # That's why we try several times to see if dictionary was 
        # filled with new data and only if it hadn't been we abort.      
        time.sleep(TimeoutSeconds);     
        
        retryCount += 1;
        continue;
      else:
        break;

    logging.info("Trying {0} ({1}/{2})".format(urlForRequest, Iterations, MaxIterations));
    
    try:
      r = requests.get(urlForRequest, timeout=TimeoutSeconds);
    except:
      logging.info("\n\n*****\nException: {0}\n*****\n".format(sys.exc_info()));      
      continue;

    if not r:
      logging.info("requests.get() failed: {0} - {1}".format(r.status_code, r.content));
      retryCount += 1;
      continue;

    try:
      meta = None;
      
      if NoMeta == False:      
        meta = GetMetadata(r.content);
        
      #print("{0} - {1}".format(urlForRequest, meta));
    except:
      logging.info("GetMetadata() failed: {0} - {1}".format(r.status_code, r.content));
      continue;

    l = FindUrls(r.content);
    
    urls = [];
    
    for item in l:
      baseUrl = GetBaseUrl(item);    
      
      if baseUrl not in Urls:
        urls.append(baseUrl);
        
    d = dict.fromkeys(urls);
    
    ThreadLock.acquire();    
    Urls.update(d);
    Urls[urlForRequest] = meta;
    Start.update(d);
    Iterations += 1;
    print(" {0} {1}/{2}\r".format(progr[Iterations % len(progr)], Iterations, MaxIterations), end="");
    ThreadLock.release();
    
    time.sleep(SleepSeconds);

  logging.info("Thread %s: finishing", name)

def SignalHandler(sig, frame):
  global ExitApp;
  global StopWriting;
  global Start;
  global MaxThreads;
  
  print("!!! SIGINT !!!");  
  if ExitApp == False:
    ExitApp = True;
    WriteResults();
  else:
    if StopWriting == False:
      StopWriting = True;

if __name__ == "__main__":
  maxJobs = 1;

  ap = argparse.ArgumentParser(description="Search the Internet for links.\nTry different combinations of threads / iterations, or run several times for best results.", formatter_class=argparse.RawTextHelpFormatter);
  ap.add_argument("START", default="http://www.yandex.ru", help="URL to start searching from (in full signature)");
  ap.add_argument("WORKERS", default=maxJobs, help="number of threads (default 1)");
  ap.add_argument("MAX_ITERATIONS", default=MaxIterations, help="maximum number of find iterations (default 10)");  
  ap.add_argument("--sleep", default=SleepSeconds, help="number of seconds to sleep after one thread work iteration (default 1.0)", required=False);
  ap.add_argument("--all", action="store_true", help="search for http and https links (default 'http only')", required=False);
  ap.add_argument("--with-meta", action="store_true", help="get <META description> text (default no)", required=False);
  ap.add_argument("--verbose", action="store_true", help="print some tech details along the way as well (default no)", required=False);
  
  res = ap.parse_args();
  
  Start[res.START] = None;
  
  maxJobs = int(res.WORKERS, 10);
  
  MaxThreads = maxJobs;
  MaxIterations = int(res.MAX_ITERATIONS, 10);
  SleepSeconds = float(res.sleep);
  
  if res.all == True:
    HttpOnly = False;
    
  if res.verbose == True:
    LogLevel = logging.INFO;
    
  if res.with_meta == True:
    NoMeta = False;
  
  print("{0} threads".format(maxJobs));    
  print("Up to {0} iterations".format(MaxIterations));
  
  format = "%(asctime)s: %(message)s";
  logging.basicConfig(format=format, level=LogLevel, datefmt="%H:%M:%S");

  signal.signal(signal.SIGINT, SignalHandler);

  threads = [];
  for index in range(maxJobs):
    t = threading.Thread(target=thread_function, args=(index,));
    threads.append(t);
    t.start();
    
  for index, thread in enumerate(threads):
    thread.join();
    
  WriteResults();
  