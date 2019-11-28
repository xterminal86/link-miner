#!/usr/bin/python3

import sys;
import logging
import threading
import time
import concurrent.futures;
import re;
import requests;
import signal;

from threading import Lock;

ThreadLock = Lock();

# Initial URL to mine from
Start = { "http://www.stoloto.ru" : None };

# Result will be stored here
Urls = {};

ExitApp = False;

# Maximum number of requests
MaxIterations = 10;

# Requests counter
Iterations = 0;

# Flag that determines if results have already been written to file
ResultsWritten = False;

# Timeout for request.get()
TimeoutSeconds = 5;

# Verbose flag sets this to logging.INFO
LogLevel = logging.CRITICAL;

def FindUrls(string):
  # findall() has been used
  # with valid conditions for urls in string
  str = string.decode("iso-8859-1");
  url = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', str);
  return url

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
  if ResultsWritten == True:
    return;
  print("Writing results ({0} links mined)...".format(len(Urls)));
  f = open("links.txt", "w");
  counter = 0;
  total = len(Urls);
  for key in Urls:
    meta = Urls[key];
    if meta is None:
      try:
        r = requests.get(key, timeout=TimeoutSeconds);
        meta = GetMetadata(r.content);
        Urls[key] = meta;
      except:
        continue;
    try:
      f.write("{0}\n>>>\n{1}\n<<<\n\n".format(key, meta));
    except:
      f.write("{0}\n>>>\n{1}\n<<<\n\n".format(key, sys.exc_info()));
      continue;
    print(" Writing {0}/{1}\r".format(counter, total), end="");
    counter += 1;
  f.close();
  print("\nDone!");
  ResultsWritten = True;

def thread_function(name):
  global ExitApp;
  global Iterations;
  global MaxIterations;
  global TimeoutSeconds;

  logging.info("Thread %s: starting", name)

  while True:
    if ExitApp == True:
      break;

    urlForRequest = [];

    if Iterations > MaxIterations:
      ThreadLock.acquire();
      ExitApp = True;
      ThreadLock.release();
      break;

    if len(Start) != 0:
      ThreadLock.acquire();
      urlForRequest = Start.popitem();
      ThreadLock.release();
    else:
      #logging.info("Thread {0} - no jobs".format(name));
      time.sleep(0.2);
      continue;

    logging.info("Trying {0} ({1}/{2})".format(urlForRequest[0], Iterations, MaxIterations));

    try:
      r = requests.get(urlForRequest[0], timeout=TimeoutSeconds);
    except:
      logging.info("\n\n*****\nException: {0}\n*****\n".format(sys.exc_info()));
      continue;

    if not r:
      logging.info("requests.get() failed: {0} - {1}".format(r.status_code, r.content));
      continue;

    try:
      meta = GetMetadata(r.content);
      #print("{0} - {1}".format(urlForRequest[0], meta));
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
    Urls[urlForRequest[0]] = meta;
    Start.update(d);
    Iterations += 1;
    ThreadLock.release();
    time.sleep(1);

  logging.info("Thread %s: finishing", name)

def SignalHandler(sig, frame):
  global ExitApp;
  print("!!! SIGINT !!!");
  WriteResults();
  ExitApp = True;

if __name__ == "__main__":
  maxJobs = 1;

  if len(sys.argv) == 1:
    print("{0} <WORKERS=1> <MAX_ITERATIONS=10> [--verbose]".format(sys.argv[0]));
    sys.exit(0);

  signal.signal(signal.SIGINT, SignalHandler);

  if len(sys.argv) > 2 and sys.argv[1].isdigit():
    maxJobs = int(sys.argv[1]);
    print("{0} threads".format(maxJobs));
    if sys.argv[2].isdigit():
      MaxIterations = int(sys.argv[2]);
      print("Up to {0} iterations".format(MaxIterations));
    if len(sys.argv) == 4 and sys.argv[3] == "--verbose":
      LogLevel = logging.INFO;

  format = "%(asctime)s: %(message)s";
  logging.basicConfig(format=format, level=LogLevel, datefmt="%H:%M:%S");

  with concurrent.futures.ThreadPoolExecutor(max_workers=maxJobs) as executor:
      executor.map(thread_function, range(maxJobs));

  WriteResults();
