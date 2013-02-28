#!/usr/bin/python2.7
#
# Script to export holds from Sierra and send them to shoutbomb
#

import os
import psycopg2
import paramiko

from datetime import date

# Shoutbomb wants blank fields not 'None'
def strify(obj):
    if obj == None:
        return ''
    else:
        return str(obj)
        
def write_file(cursor, name, title_row, query):
    # move old files
    os.system("mv %s*.txt archive/" % name)
    filename = ("%s%s.txt" % (name, date.today(),))
    try:
        cursor.execute(query)
        rows = cursor.fetchall()

        f = open(filename, "w")
    
        f.write(title_row)

        for r in rows:
            # strify in case we get back some numbers
            f.write("|".join(map(strify, r)))
            f.write("\n")

        f.close()
    except:
        # if we fail don't return a file name
        return None
    return filename


def put_file(sftp, filename):
    if filename != None:
        # name depends on your destination
        sftp.put(filename, ("/usr/home/spl/shoutbomb/%s" % filename))

try:
    # insert your user, host, password
    conn = psycopg2.connect("dbname='iii' user='' host='' port='1032' password='' sslmode='require'")
except psycopg2.Error as e:
    print "Unable to connect to database: " + unicode(e)

cursor = conn.cursor()

holds_titles = "title|last_update|item_no|patron_no|pickup_location"
# ILL titles are in varfield but normal titles in subfield.
holds_q = """SELECT TRIM(TRAILING '/' from COALESCE(s.content, v.field_content)), 
             to_char(rmi.record_last_updated_gmt,'MM-DD-YYYY') AS last_update, 
             'i' || rmi.record_num || 'a' AS item_no, 
             'p' || rmp.record_num || 'a' AS patron_no, 
             h.pickup_location_code AS pickup_location 
   FROM sierra_view.hold AS h JOIN sierra_view.patron_record AS p ON ( p.id = h.patron_record_id ) 
   JOIN sierra_view.record_metadata AS rmp ON (rmp.id = h.patron_record_id AND rmp.record_type_code = 'p') 
   JOIN sierra_view.item_record AS i ON ( i.id = h.record_id ) 
   JOIN sierra_view.bib_record_item_record_link AS bil ON ( bil.item_record_id = i.id AND bil.bibs_display_order = 0 ) 
   LEFT JOIN sierra_view.subfield AS s ON (s.record_id = bil.bib_record_id AND s.marc_tag='245' AND s.tag = 'a') 
   LEFT JOIN sierra_view.varfield AS v ON (v.record_id = bil.bib_record_id AND v.varfield_type_code = 't' AND v.marc_tag IS NULL)
   JOIN sierra_view.record_metadata AS rmi ON ( rmi.id = i.id AND rmi.record_type_code = 'i') 
   WHERE i.item_status_code = '!'"""

overdues_titles = "patron_no|item_barcode|title|due_date|item_no|money_owed|loan_rule|item_holds|bib_holds|renewals|bib_no"
overdues_q =  """SELECT 'p' || rmp.record_num || 'a' AS patron_no, 
                 replace(ib.field_content,' ','') AS item_barcode, 
                 TRIM(TRAILING '/' from COALESCE(s.content, v.field_content)) AS title, 
                 to_char(c.due_gmt,'MM-DD-YYYY') AS due_date, 
                 'i' || rmi.record_num || 'a' AS item_no, 
                 round(p.owed_amt,2) AS money_owed, 
                 c.loanrule_code_num AS loan_rule, 
                 nullif (count(ih.id),0) AS item_holds, 
                 nullif (count(bh.id),0) AS bib_holds, 
                 c.renewal_count AS renewals, 'b' || rmb.record_num || 'a' AS bib_no 
  FROM sierra_view.checkout AS c 
  JOIN sierra_view.patron_record AS p ON (p.id = c.patron_record_id) 
  JOIN sierra_view.record_metadata AS rmp ON (rmp.id = c.patron_record_id AND rmp.record_type_code = 'p') 
  JOIN sierra_view.item_record AS i ON (i.id = c.item_record_id) 
  JOIN sierra_view.record_metadata AS rmi ON (rmi.id = i.id AND rmi.record_type_code = 'i') 
  JOIN sierra_view.varfield AS ib ON (ib.record_id = i.id AND ib.varfield_type_code = 'b') 
  JOIN sierra_view.bib_record_item_record_link AS bil ON (bil.item_record_id = i.id) 
  LEFT JOIN sierra_view.subfield AS s ON (s.record_id = bil.bib_record_id AND s.marc_tag='245' AND s.tag = 'a') 
  LEFT JOIN sierra_view.varfield AS v ON (v.record_id = bil.bib_record_id AND v.varfield_type_code = 't' AND v.marc_tag IS NULL)
  LEFT JOIN sierra_view.hold as bh ON (bh.record_id = bil.bib_record_id) 
  LEFT JOIN sierra_view.hold as ih ON (ih.record_id = i.id and ih.status = '0') 
  LEFT JOIN sierra_view.record_metadata as rmb ON (rmb.id = bil.bib_record_id AND rmb.record_type_code = 'b') 
  WHERE (current_date - c.due_gmt::date) = 7 
  GROUP BY 1,2,3,4,5,6,7,10,11 
  ORDER BY patron_no"""

renewals_titles = "patron_no|item_barcode|title|due_date|item_no|money_owed|loan_rule|item_holds|bib_holds|renewals|bib_no"
renewals_q = """SELECT 'p' || rmp.record_num || 'a' AS patron_no,
                replace(ib.field_content,' ','') AS item_barcode,
                TRIM(TRAILING '/' from COALESCE(s.content, v.field_content)) AS title,
                to_char(c.due_gmt,'MM-DD-YYYY') AS due_date,
                'i' || rmi.record_num || 'a' AS item_no,
                round(p.owed_amt,2) AS money_owed,
                c.loanrule_code_num AS loan_rule,
                nullif (count(ih.id),0) AS item_holds,
                nullif (count(bh.id),0) AS bib_holds,
                c.renewal_count AS renewals,
                'b' || rmb.record_num || 'a' AS bib_no
  FROM sierra_view.checkout AS c
  JOIN sierra_view.patron_record AS p ON (p.id = c.patron_record_id)
  JOIN sierra_view.record_metadata AS rmp ON (rmp.id = c.patron_record_id AND rmp.record_type_code = 'p')
  JOIN sierra_view.item_record AS i ON (i.id = c.item_record_id)
  JOIN sierra_view.record_metadata AS rmi ON (rmi.id = i.id AND rmi.record_type_code = 'i')
  JOIN sierra_view.varfield AS ib ON (ib.record_id = i.id AND ib.varfield_type_code = 'b')
  JOIN sierra_view.bib_record_item_record_link AS bil ON (bil.item_record_id = i.id)
  LEFT JOIN sierra_view.subfield AS s ON (s.record_id = bil.bib_record_id AND s.marc_tag='245' AND s.tag = 'a')
  LEFT JOIN sierra_view.varfield AS v ON (v.record_id = bil.bib_record_id AND v.varfield_type_code = 't' AND v.marc_tag IS NULL)
  LEFT JOIN sierra_view.hold as bh ON (bh.record_id = bil.bib_record_id) 
  LEFT JOIN sierra_view.hold as ih ON (ih.record_id = i.id and ih.status = '0')         
  LEFT JOIN sierra_view.record_metadata as rmb ON (rmb.id = bil.bib_record_id AND rmb.record_type_code = 'b')
  WHERE (c.due_gmt::date - current_date) = 1
  GROUP BY 1,2,3,4,5,6,7,10,11
  ORDER BY patron_no"""

holds_file = write_file(cursor, "holds", holds_titles, holds_q)
overdues_file = write_file(cursor, "overdues", overdues_titles, overdues_q)
renewals_file = write_file(cursor, "renewals", renewals_titles, overdues_q)

ssh = paramiko.SSHClient() 
ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
# insert shoutbomb server, your username, password
ssh.connect("", username="", password="")
sftp = ssh.open_sftp()

put_file(sftp, holds_file)
put_file(sftp, overdues_file)
put_file(sftp, renewals_file)

sftp.close()
ssh.close()