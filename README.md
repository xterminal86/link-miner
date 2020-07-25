# link-miner

A simple script that tries to collect links from the Internet (sorta).

First it starts from some website you specify as a parameter, then it tries to find all links referenced on this site by scanning web page's contents. 
Then the same operation is repeated against all found links.
Maximum number of such iterations can also be specified as a parameter.

In the end it didn't work out the way I expected - basically after any number of iterations you get the same set of links found, regardless of starting site. 
Probably this is because of cyclic references happening somewhere along the way, I don't know...
