#!/usr/bin/env python3

import sys
import smtplib
import imaplib
import time
import sqlite3

from optparse import OptionParser
from email.mime.text import MIMEText

parser = OptionParser(usage="""Usage: %prog [options] arg""")
parser.add_option('-s', '--smtp-server',
	type='string', action='store', dest='server',
	help="""SMTP server to use for sending message""")
parser.add_option('-f', '--from-address',
	type='string', action='store', dest='sender',
	default='user@domain.tld',
	help="""email address to use as sender""")
parser.add_option('-t', '--to-address',
	type='string', action='store', dest='recipient',
	default='user@domain.tld',
	help="""email address to use as recipient""")
parser.add_option('-i', '--imap-server',
	type='string', action='store', dest='imap',
	help="""IMAP server from where to retrieve the message""")
parser.add_option('-u', '--username',
	type='string', action='store', dest='user',
	default='user',
	help="""user name for IMAP authentication""")
parser.add_option('-p', '--password',
	type='string', action='store', dest='passwd',
	default='password',
	help="""password for IMAP authentication""")
parser.add_option('-x', '--imap-ssl',
	action='store_true', dest='ssl', default=False,
	help="""use SSL when connecting to IMAP server""")
parser.add_option('-d', '--database',
	type='string', action='store', dest='database',
	help="""where to store the message id's""")
opts, args = parser.parse_args()
if not opts.server and not opts.imap and not opts.database:
    parser.print_help()
    sys.exit(1)

# generate new id
msgid = time.time()

# create the database if it doesn't exist already
conn = sqlite3.connect(opts.database)
createdb = '''create table if not exists ids
 (id, retrieved)'''
c = conn.cursor()
c.execute(createdb)
conn.commit()

# send message with new id
subject = 'Email ID#%s' % msgid
msg = MIMEText('Please ignore me.')
msg['Subject'] = subject
msg['From'] = opts.sender
msg['To'] = opts.recipient
try:
    s = smtplib.SMTP(opts.server)
    s.send_message(msg)
    s.quit()
except:
    print("WARNING: Error sending mail")
    sys.exit(1)

# add sent date to the database
t = (msgid, 0)
c.execute('insert into ids values (?,?)', t)
conn.commit()

# now check if previous messages arrived
try:
	if opts.ssl:
		imap = imaplib.IMAP4_SSL(host=opts.imap)
	else:
		imap = imaplib.IMAP4(host=opts.imap)
except:
	print("WARNING: Error connecting to IMAP server")
	sys.exit(1)

try:
	imap.login(opts.user, opts.passwd)
except:
	print("WARNING: IMAP login failed")
	sys.exit(1)

# login succeeded, working on inbox
imap.select()

# set up our counters
lostcount = 0
retcount = 0

# get the ids we want from the db
c.execute('select id from ids where retrieved=0')
r = c.fetchall()
i = len(r)

while i > 0:
	# look for each non retrieved message
	lostcount = lostcount + 1
	typ, data = imap.search(None, '(SUBJECT "ID#' + str(r[i-1][0]) +'")')
	if data[0]:
		# found it, mark it as retrieved in the db...
		c.execute('update ids set retrieved=1 where id=?', (r[i-1][0],))
		conn.commit()
		# ...and delete from message store
		imap.store(data[0], '+FLAGS', '\\Deleted')
		imap.expunge()
		# update counters
		retcount = retcount + 1
		i = i - 1
	else:
		i = i - 1

waitingfor = lostcount - retcount
print('Retrieved ' + str(retcount) + ' message(s)')
print('Waiting for ' + str(waitingfor) + ' message(s)')
imap.logout()

# do some housekeeping before closing db connection
# XXX delete retrieved entries older than whatever...
c.close()

sys.exit(0)

