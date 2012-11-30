#! /usr/bin/python3
'''A lightweight MIPS assembler'''

import argparse
import os.path
import io
import re
import collections
import sys

debug = True

listeq = lambda x, y: collections.Counter(x) == collections.Counter(y)

regs = (
	'$zero','$at','$v0','$v1','$a0','$a1','$a2','$a3',
	'$t0','$t1','$t2','$t3','$t4','$t5','$t6','$t7',
	'$s0','$s1','$s2','$s3','$s4','$s5','$s6','$s7',
	'$t8','$t9','$k0','$k1','$gp','$sp','$fp','$ra'
)

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
#	parser.add_argument('-c', metavar='MARS',
#						help='compare output to MARS hex file',
#						type=argparse.FileType('r'))
	args = parser.parse_args()

	isa = get_mips_isa() # make a dictionary of ISA commands and their encodings
	
	# form the output file if not supplied
	if not args.out:
		args.out = open(os.path.splitext(args.asm.name)[0] + '.hex', 'w')

	for i, line in enumerate(args.asm):
		if re.match('\s*[#\n\r]', line): # skip comments and blank lines
			continue
		print('-'*24) if debug else None
		try:
			binstr = get_encoding(line.strip(), isa)
		except:
			args.asm.close()
			args.out.close()
			os.remove(args.out.name)
			raise
			#sys.exit('Unexpected Error:' + str(sys.exc_info()[0]))
		if binstr:
			print(binstr)  if debug else None
			hexstr = binstr2hexstr(binstr)
			print(hexstr)  if debug else None
			args.out.write(hexstr + '\n')

	#if args.c:
		#print(args.c.name)
		#print(args.out.name)
		#if filecmp.cmp(args.c.name, args.out.name, shallow=True):
			#print('Files are identical')
		#else:
			#print('Files differ')
			
	args.asm.close()
	args.out.close()


def binstr2hexstr(binstr, hexdigs=8):
	hexstr = str('%'+str(hexdigs)+'s') % hex(int(binstr, 2))[2:]	# form the hex number
	return re.sub('\s', '0', hexstr)


# takes a string and breaks it into a command name and its arguments
def parse_cmd(line, reg_replace=False):
	line = re.sub('#.*', '', line) # handle in-line comments
	line = re.sub('[,\(\)]', ' ', line) # handle commas and parens
	cmd = re.split('\s+', line.strip())
	if reg_replace: # try to replace a named register with its numerical value
		if len(cmd) != 1:
			args = cmd[1:]
			for i,a in enumerate(args):
				#skip non-reg args and $0 to $31
				if re.match('\$0*([0-9]|[12][0-9]|3[01])', a) or re.match('(?!\$)', a): 
					#print('skipping \''+ a + '\'')
					continue
				try:
					args[i] = '$' + str(regs.index(a))
				except ValueError:
					raise #TODO: properly alert user to invalid named register
			cmd[1:] = args
	return cmd


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
			args[i] = re.sub('[\w\-]+', 'i', a) # immediate values indicated with 'i'
		fmt[1:] = args
	return fmt



def find_cmd(asm, isa):
	'''
	validates a parsed command by checking it against the ISA
	args:
		asm = unparsed line from ASM file
		isa = the ISA dictionary
	returns:
		key-value tuple from ISA matching the ASM command
	'''
	cmd = parse_cmd_fmt(asm)
	for k,v in isa.items():
		isa_cmd = parse_cmd_fmt(k)
		if listeq(isa_cmd, cmd):
			print('find_cmd(): %s -> %s' % (k,v))  if debug else None
			return (k,v)
	return (None, None)


def get_encoding(asm, isa):
	'''
	returns the hex encoding for the given ASM line, if possible
	args:
		asm = unparsed line from ASM file
		isa = the ISA dict
	returns:
		string representing the binary encoding of the ASM line
	'''
	isa_key, binstr = find_cmd(asm, isa)
	if isa_key:
		isa_cmd = parse_cmd(isa_key)
		asm_cmd = parse_cmd(asm, reg_replace=True)
		print(asm_cmd)  if debug else None
		#print(binstr)
	else:
		print('Command not found: ' + asm)
		return None
	for asm_arg, isa_arg in zip(asm_cmd[1:], isa_cmd[1:]):
		binstr = put_arg(re.sub('\$', '', asm_arg), 
						re.sub('\$', '', isa_arg), 
						binstr)
	return re.sub('-', '0', binstr) # replace don't cares ('-') with zeros


def put_arg(val, sym, binstr):
	n = binstr.count(sym)	# get the length of the binary number
	b = int2twoscomp(int(val), n)
	print('%s\t%s\t%s' % (val, sym, b))  if debug else None
	return re.sub(sym + '+', b, binstr)


def int2twoscomp(val, nbits):
	b = bin(abs(val))[2:]
	b = str('%'+str(nbits)+'s') % b
	b = re.sub('\s', '0', b)
	#print(b)  if debug else None
	if val < 0:
		b = twoscomp(b)
	return b


def onescomp(binstr):
    return ''.join('1' if b=='0' else '0' for b in binstr)

def twoscomp(binstr):
    return bin(int(onescomp(binstr),2)+1)[2:]
    
def get_mips_isa():
	with open('mips_isa.txt', 'r') as f:
		isa = {}
		for line in f:
			if re.match('\s*[#\n\r]', line): # skip comments and blank lines
				continue
			k, v = line.strip().split('=')
			isa[k.strip()] = v.strip()
	return isa


if __name__ == '__main__':
	main()
