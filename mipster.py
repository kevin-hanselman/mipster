#! /usr/bin/python3
'''A lightweight MIPS assembler'''

import argparse
import os.path
import io
import re
import collections

listeq = lambda x, y: collections.Counter(x) == collections.Counter(y)

def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('-v', '--version', action='version', 
						version='%(prog)s 0.1')
	parser.add_argument('asm',	help='MIPS assembly input file',
						type=argparse.FileType('r'))
	parser.add_argument('-o', '--out',
						metavar='HEX',
						help='name of the output file',
						type=argparse.FileType('w'))
	args = parser.parse_args()

	isa = get_mips_isa() # make a dictionary of ISA commands and their encodings

	# form the output file if not supplied
	if not args.out:
		args.out = open(os.path.splitext(args.asm.name)[0] + '.hex', 'w')

	for i, line in enumerate(args.asm):
		if re.match('\s*[#\n\r]', line): # skip comments and blank lines
			continue
		print('-'*15)
		binstr = get_encoding(line.strip(), isa)
		if binstr:
			print(binstr)
			hexstr = binstr2hexstr(binstr)
			print(hexstr)
			args.out.write(hexstr + '\n')

	args.asm.close()
	args.out.close()

def binstr2hexstr(binstr, hexdigs=8):
	hexstr = str('%'+str(hexdigs)+'s') % hex(int(binstr, 2))[2:]	# form the hex number
	return re.sub('\s', '0', hexstr)
	
	
# takes a string and breaks it into a command name and its arguments
def parse_cmd(line):
	line = re.sub('#.*', '', line) # handle in-line comments
	line = re.sub(',', ' ', line) # handle commas
	return re.split('\s+', line.strip())


def parse_cmd_fmt(line):
	#line = re.sub('#.*', '', line) # handle in-line comments
	#line = re.sub(',', ' ', line) # handle commas
	#line = re.sub('\$\w+', '$', line) # register args indicated with just '$'
	#line = re.sub('\w+(?=$)', 'i', line) # immediate values indicated with 'i'
	#return re.split('\s+', line.strip())
	fmt = parse_cmd(line)
	if len(fmt) != 1:
		args = fmt[1:]
		for i,a in enumerate(args):
			args[i] = re.sub('\$\w+', '$', a)
			args[i] = re.sub('\w+', 'i', a)
		fmt[1:] = args
	return fmt


# validates a parsed command by checking it against the ISA
# args:
#	asm = unparsed line from ASM file
#	isa = the ISA dictionary
# returns:
#	key-value tuple from ISA matching the ASM command
def find_cmd(asm, isa):
	cmd = parse_cmd_fmt(asm)
	print(cmd)
	for k,v in isa.items():
		isa_cmd = parse_cmd_fmt(k)
		if listeq(isa_cmd, cmd):
			print('%s -> %s' % (k,v))
			return (k,v)
	return (None, None)


# returns the hex encoding for the given ASM line, if possible
# args:
#	asm = unparsed line from ASM file
#	isa = the ISA dict
# returns:
#	string representing the hexadecimal encoding of the ASM line
def get_encoding(asm, isa):
	isa_key, binstr = find_cmd(asm, isa)
	if isa_key:
		isa_cmd = parse_cmd(isa_key)
		asm_cmd = parse_cmd(asm)
		print(asm_cmd)
		print(binstr)
	else:
		print('Command not found: ' + asm)
		return None
	for asm_arg, isa_arg in zip(asm_cmd[1:], isa_cmd[1:]):
		binstr = put_arg(re.sub('\$', '', asm_arg), 
						re.sub('\$', '', isa_arg), 
						binstr)
	return binstr
	

def put_arg(val, sym, binstr):
	n = binstr.count(sym)	# get the length of the binary number 
	substr = str('%'+str(n)+'s') % bin(int(val))[2:]	# form the binary number
	substr = re.sub('\s', '0', substr)
	print('%s\t%s\t%s' % (val, sym, substr))
	return re.sub(sym + '+', substr, binstr)


def get_mips_isa():
	with open('mips_isa.txt', 'r') as f:
		isa = {}
		for line in f:
			k, v = line.strip().split('=')
			isa[k.strip()] = v.strip()
	return isa


if __name__ == '__main__':
	main()
