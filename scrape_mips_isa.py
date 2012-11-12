#! /usr/bin/python3

from urllib.request import urlopen
from bs4 import BeautifulSoup
import re

url = 'http://www.mrc.uidaho.edu/mrc/people/jff/digital/MIPSir.html'

page = urlopen(url)
soup = BeautifulSoup(page) # scrape page

cmds = soup.find_all(class_='MsoNormalTable') #scrape tables

# open the output file
with open('mips_isa.txt', 'w') as f:
  for cmd in cmds: # scrape ISA commands
    syntax = cmd.find('tr', style=re.compile('irow:2')).find_all('td')[-1].strings
    syntax = re.sub('[\n\r,]','',''.join(syntax)).strip()
    #print(repr(syntax))
    
    binary = cmd.find('code').strings
    binary = re.sub('[\n\r\s]+','',''.join(binary))
    #print(repr(binary))
    
    fmt_str = syntax + '=' + binary + '\n'
    print(fmt_str)
    f.write(fmt_str)