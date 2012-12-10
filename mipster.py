#! /usr/bin/python3
'''
A lightweight MIPS assembler

[Author: Kevin Hanselman]
'''

import argparse
import os.path
import io
import re
import collections
import tempfile

text_start_addr = 0x00400000 # starting address for the .text segment
data_start_addr = 0x00001001 # starting address for the .data segment

data_seg = []
data_labels = [] # holds each label in the .data segment of ASM file, indexed by line number
text_labels = [] # holds each label in the .text segment of ASM file, indexed by line number

listeq = lambda x, y: collections.Counter(x) == collections.Counter(y)

regs = (
	'$zero','$at','$v0','$v1','$a0','$a1','$a2','$a3',
	'$t0','$t1','$t2','$t3','$t4','$t5','$t6','$t7',
	'$s0','$s1','$s2','$s3','$s4','$s5','$s6','$s7',
	'$t8','$t9','$k0','$k1','$gp','$sp','$fp','$ra'
)

class ASMError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return str(self.value)

def main():
	global debug
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('-v', '--version', action='version',
						version='%(prog)s 0.3')
	parser.add_argument('-D', '--Debug', action='store_true',
						help='output debug information')
	parser.add_argument('asm',	help='MIPS assembly input file',
						type=argparse.FileType('r'))
	parser.add_argument('-o', '--out',
						metavar='HEX',
						help='name of the text segment output file',
						type=argparse.FileType('w'))
	parser.add_argument('-d', '--data',
						metavar='HEX',
						help='name of the data segment output file',
						type=argparse.FileType('w'))
#	parser.add_argument('-c', metavar='MARS',
#						help='compare output to MARS hex file',
#						type=argparse.FileType('r'))
	args = parser.parse_args()
	debug = args.Debug
	isa = get_mips_isa() # make a dictionary of ISA commands and their encodings

	# form the output file if not supplied
	if not args.out:
		args.out = open(os.path.splitext(args.asm.name)[0] + '_txt.hex', 'w')
	
	if not args.data:
		args.data = open(os.path.splitext(args.asm.name)[0] + '_dat.hex', 'w')

	#tmp = tempfile.NamedTemporaryFile('r+', delete=False)
	tmp = open(os.path.splitext(args.asm.name)[0] + '.tmp', 'w+')
	
	try:
		asm2basic(args.asm, tmp, isa)
		tmp.seek(0)
		get_labels(tmp)
	except Exception as ex:
		args.asm.close()
		args.out.close()
		args.data.close()
		tmp.close()
		#os.remove(tmp.name)
		os.remove(args.out.name)
		os.remove(args.data.name)
		if isinstance(ex, ASMError):
			print(ex)
			return
		else:
			raise
	
	tmp.seek(0)

	# create hex output
	j = 0 # ASM command index/line number
	data = False
	for i, line in enumerate(tmp):
		line = line.strip()
		if re.match('\.data', line):
			data = True
		if re.match('\.text', line):
			data = False
		# skip comments, blank lines, lone labels, and headers
		if re.match('(?:#.*)?$', line) \
			or re.match('\w+:\s*(?:#.*)?$', line) \
			or re.match('\.\w+', line) \
			or data:
			continue
		print('i=%d j=%d '%(i,j) + '-'*70) if debug else None
		try:
			binstr = get_encoding(line, j, isa)
		except Exception as ex:
			args.asm.close()
			args.out.close()
			args.data.close()
			tmp.close()
			#os.remove(tmp.name)
			os.remove(args.out.name)
			os.remove(args.data.name)
			if isinstance(ex, ASMError):
				print(ex)
				return
			else:
				raise
		if binstr:
			hexstr = binstr2hexstr(binstr)
			print('%s -> %s' % (hexstr, binstr)) if debug else None
			args.out.write(hexstr + '\n')
		j += 1
	
	for n in data_seg:
		args.data.write(int2hexstr(int(n)) + '\n')
	
	args.asm.close()
	args.out.close()
	tmp.close()
	os.remove(tmp.name)
	print('data_seg = %r' % data_seg) if debug else None
	print('Assembler successful!')

def asm2basic(infile, outfile, isa):
	text = False
	for i, line in enumerate(infile):
		line = clean_line(line)
		if re.match('(?:#.*)?$', line): # skip comments and blank lines
			continue
		m = re.match('\.\w+', line)
		if m:
			if m.group(0) == '.text':
				text = True
				data = False
			elif m.group(0) == '.data':
				data = True
				text = False
		if text:
			isa_key, isa_val = find_cmd(line, isa)
			if isa_val:
				if re.match('[^01]', isa_val):
					m = re.match('\w+:', line)
					if m:
						outfile.write(m.group(0) + '\n')
					cmds = pseudo2real(line, isa_key, isa_val)
					print(cmds) if debug else None
					for c in cmds:
						outfile.write(c + '\n')
					continue
		outfile.write(line + '\n')

def get_labels(infile):
	skip = False
	text = False
	data = False
	for i, line in enumerate(infile):
		line = clean_line(line)
		if re.match('(?:#.*)?$', line): # skip comments and blank lines
			#print('skipping %r' % line) if debug else None
			continue
		m = re.match('\.\w+', line)
		if m:
			if m.group(0) == '.text':
				text = True
				data = False
			elif m.group(0) == '.data':
				data = True
				text = False
			elif data:
				data_seg.extend([x for x in re.split('\s+', line)[1:] if x.isdigit()])
				data_labels.extend([None for x in re.split('\s+', line)[1:] if x])
			continue
		if skip and text:
			skip = False
			continue
		m = re.match('(\w+):($)?', line)
		if m:
			if m.group(2) is None: # if no match, label has text on same line
				skip = False
			elif not m.group(2): # if matched EOL, label goes w/ next line, skip
				skip = True
			if data:
				try:
					data_labels.pop() if not data_labels[-1] else None
				except IndexError:
					pass
				data_labels.append(m.group(1))
				# add Nones for each data element
				if not skip:
					data_seg.extend([x for x in re.split('\s+', line)[2:] if x.isdigit()])
					data_labels.extend([None for x in re.split('\s+', line)[2:] if x])
			else: # default to .text segment, even if not explicitly declared
				text_labels.append(m.group(1))
		else:
			if data:
				data_labels.append(None)
			else: # default to .text segment, even if not explicitly declared
				text_labels.append(None)
	print('text_labels = %r\ndata_labels = %r' % (text_labels, data_labels)) if debug else None

def pseudo2real(asm, isa_key, isa_val):
	#isa_cmds = list of strings, each representing an ASM command
	asm_cmd = parse_cmd(asm)
	pseudo_cmd = parse_cmd(isa_key)
	isa_cmds = [parse_cmd(x) for x in re.split(';', isa_val)]

	# loop through real instructions
	for i, isa_cmd in enumerate(isa_cmds):
		# loop through arguments
		for asm_arg, pseudo_arg in zip(asm_cmd[1:], pseudo_cmd[1:]):
			if pseudo_arg in isa_cmd[1:]:
				arg_idx = isa_cmd[1:].index(pseudo_arg) + 1
				isa_cmds[i][arg_idx] = asm_arg
	return [' '.join(x) for x in isa_cmds]

def binstr2hexstr(binstr, hexdigs=8):
	hexstr = str('%'+str(hexdigs)+'s') % hex(int(binstr, 2))[2:] # form the hex number
	return re.sub('\s', '0', hexstr)

def int2hexstr(i, hexdigs=8):
	hexstr = str('%'+str(hexdigs)+'s') % hex(i)[2:] # form the hex number
	return re.sub('\s', '0', hexstr)

def translate_cmd(line, linenum):
	cmd = parse_cmd(line)
	if len(cmd) > 1:
		args = cmd[1:]
		for i,a in enumerate(args):
			# skip $0 to $31 and non-register numeric arguments
			if re.match('\$0*([0-9]|[12][0-9]|3[01])$', a) or re.match('(?!\$)\d+', a):
				continue
			if re.match('(?!\$)-?\d+', a): # immediate value
				continue
			if re.match('D', a):
				args[i] = str(data_start_addr)
			elif re.match('(?!\$)\w+', a): # if alphanumeric string, treat as label
				if a in text_labels:
					li = text_labels.index(a)
					t = True
				elif a in data_labels:
					li = data_labels.index(a)
					t = False
				else:
					raise ASMError('Label %r not found' % a)
					#print('label index= %r' % repr(li))
				if re.match('j', cmd[0]): # jump uses a direct address
					# index * number of bytes per instruction + starting address
					# right shift 2 bits to fit in 26-bit 'pseudo address'
					if t:
						args[i] = str(int((li*4+text_start_addr)/4))
					else:
						ASMError('Trying to jump to a data address')
						#args[i] = str(int((li*4+data_start_addr)/4))
				elif re.match('b', cmd[0]): # branch uses an offset
					if t:
						args[i] = str(li - linenum - 1)
					else:
						raise ASMError('Trying to branch to a data address')
				else: # default to index value * 4 for instruction address
					args[i] = str(li*4)
			else:
				try:
					args[i] = '$' + str(regs.index(a))
				except ValueError:
					raise ASMError('Invalid register %r' % a)
		cmd[1:] = args
	return cmd

def clean_line(line):
	line = re.sub('[,\(\)]', ' ', line)
	line = re.sub('#.*', '', line) # handle in-line comments
	return re.sub('\s+', ' ', line.strip()) # handle commas and parens
	
def parse_cmd(line):
	'''takes a string and breaks it into a command name and its arguments'''
	line = re.sub('^\w+:', '', line)
	line = re.sub('#.*', '', line) # handle in-line comments
	line = re.sub('[,\(\)]', ' ', line) # handle commas and parens
	return re.split('\s+', line.strip())
	
def parse_cmd_fmt(line):
	fmt = parse_cmd(line)
	if len(fmt) != 1:
		args = fmt[1:]
		for i,a in enumerate(args):
			args[i] = re.sub('\$\w+', '$', a)
			args[i] = re.sub('[\w\-]+', 'i', a) # immediate values indicated with 'i'
		fmt[1:] = args
	return fmt

def find_cmd(asm, isa):
	global debug
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

def get_encoding(asm, linenum, isa):
	global debug
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
		#if re.match('[01]+', isa_value): # single, non-pseudo instruction
		isa_cmd = parse_cmd(isa_key)
		asm_cmd = translate_cmd(asm, linenum)
		print(asm_cmd)  if debug else None
	else:
		raise ASMError('Command not found: ' + asm)
	for asm_arg, isa_arg in zip(asm_cmd[1:], isa_cmd[1:]):
		binstr = put_arg(re.sub('\$', '', asm_arg),
						re.sub('\$', '', isa_arg),
						binstr)
	return re.sub('-', '0', binstr) # replace don't cares ('-') with zeros

#def pseudo2real(asm, isa_value):
	
	
def put_arg(val, sym, binstr):
	global debug
	#print('val=%r\tsym=%r\tbinstr=%r' % (val,sym,binstr))
	n = binstr.count(sym)	# get the length of the binary number
	if not n:
		raise ASMError('DEV: put_arg(): sym %r not found' % sym)
	b = int2twoscomp(int(val), n)
	print('%s\t%s\t%s' % (val, sym, b))  if debug else None
	out = re.sub(sym + '+', b, binstr)
	#print(out)
	return out

def int2twoscomp(val, nbits):
	global debug
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
