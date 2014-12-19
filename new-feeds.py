#!/usr/bin/python2.7
#
# Export enhanced new item rss feeds that include images and descriptions
#
# queries.py contains query bases and special clauses that are also used to create new item searches
# for a variety of item types and categories
#
# results must be written somewhere web accessible for now http://artemis.skokielibrary.info/new-feeds/*.xml
# these are not currently used anywhere but they could be!
#

import psycopg2
import PyRSS2Gen
import xml.etree.ElementTree as ET

import re, os
import datetime
import urllib2

from settings import *
from queries import *

def trim_summary(summary, url):
    last_space = summary.rfind(". ", 120, 200)
    if last_space > -1:
        return summary[:last_space] + (" ...")
    return summary

def read_summary(url):
    summary = ""
    try:
        f = urllib2.urlopen(url % "xml")
        xml = f.read()
        f.close()
        root = ET.fromstring(xml)
        for i in root.iter("Fld520"):
            summary = trim_summary(i[0].text, (url % "html"))
    except:
        pass
    return summary

def get_summary(isbn, upc):
    summary = ""
    if isbn != None:
        summary = read_summary("http://www.syndetics.com/index.aspx?isbn=" + unicode(isbn) + "/summary.%s&client=skopl")
    if len(summary) < 1 and upc != None:
        summary = read_summary("http://plus.syndetics.com/index.php?isbn=/avsummary.%s&client=skopl&upc=" + unicode(upc))
    return summary

def test_img_url(url):
    try:
        print url
        imgstr = urllib2.urlopen(url).read()
        if len(imgstr) > 100:
            return url
    except IOError:
        print "IOError : " + url
    return None

def image_url(isbn, upc):
    img_link = None
    if not isbn == None:
        img_link = test_img_url("http://www.syndetics.com/index.aspx?isbn=%s/LC.GIF&client=skopl" % isbn)
    if not img_link and not upc == None:
        img_link = test_img_url("http://plus.syndetics.com/index.php?isbn=/lc.gif&client=skopl&upc=%s" % upc)
    return img_link

def write_rss(cursor, filename, title, q):
    print title
    cursor.execute(q)
    rows = cursor.fetchall()

    rss = PyRSS2Gen.RSS2(
        title = "New %s at Skokie Public Library" % title,
        link = "http://encore.skokielibrary.info",
        description = "These are the lastest titles added to the collection",
        language = "eng",
        lastBuildDate = datetime.datetime.now(),
        items = [])

    for r in rows:
        link = "http://encore.skokielibrary.info/iii/encore/record/C__Rb%s" % r[0]
        item = PyRSS2Gen.RSSItem(
            title = "%s / %s" % (r[1], r[2]) if r[2] and len(r[2]) > 0 else r[1],
            link = link,
            description = """<div class="feed-item"><div class="item-image"><img src="%s"></div><div class="item-title"><a href="%s">%s</a></div><p class="item-description">%s</p></div>""" % (image_url(r[3], r[4]),link,r[1], trim_summary(r[5], link) if r[5] else get_summary(r[3], r[4]),),
            )
        rss.items.append(item)

    f = open("%s.xml" % filename, "w")
    rss.write_xml(f, encoding='utf-8')
    f.close()

try:
    conn = psycopg2.connect("dbname='%s' user='%s' host='%s' port='1032' password='%s' sslmode='require'" % (DB_NAME, DB_USER, DB_HOST, DB_PASSWORD,))
except psycopg2.Error as e:
    print "Unable to connect to database: " + unicode(e)

cursor = conn.cursor()

os.chdir(FEEDS_DIR)

for f in feeds:
    feed = feeds[f]
    write_rss(cursor, f, feed['title'], base_feed_q % ((joins[f] if f in joins else ""), feed['days'], where[f]))

cursor.close()
conn.close()
