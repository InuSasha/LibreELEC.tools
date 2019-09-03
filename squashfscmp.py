#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import os, sys, codecs, re
import subprocess

MAPKERNEL = (os.environ.get("NOMAPKERNEL",None) is None)
MAPSONAME = (os.environ.get("NOMAPSONAME",None) is None)
MISSING   = (os.environ.get("NOMISSING",None) is None)
NONEW     = (os.environ.get("NONEW",None) is not None)
NAMESORT  = (os.environ.get("NAMESORT",None) is not None)
MINDELTA  = abs(int(os.environ.get("MINDELTA","2048")))
COLOR     = (os.environ.get("COLOR","ON").upper() in ["ALWAYS", "ON", "YES", "TRUE", "1"])

BELOW_THRESHOLD = 0
SONAME_WARNING = False

re_parse = re.compile("([^ ]*) +([^ ]*) +([^ ]*) +([^ ]*) +([^ ]*) +([^ ]*) +([^ ]*) +([^ ]*) +(.*)$")
re_sonameM = re.compile("(.*)([\._-])([0-9]*\.[0-9]*)(\.so)$")
re_soname3 = re.compile("(.*\.so)(\.)([0-9]*\.[0-9]*\.[0-9]*)$")
re_soname2 = re.compile("(.*\.so)(\.)([0-9]*\.[0-9]*)$")
re_soname1 = re.compile("(.*\.so)(\.)([0-9]*)$")
re_kmodule = re.compile("^(.*/lib/modules/)([^/]*)(/.*\..*)$")

LABELS = {"missing": "MISSING",
          "new":     "NEW FILE",
          "size":    "SIZE CHANGE",
          "kernel":  "KERNEL CHANGE",
          "soname":  "SONAME CHANGE",
          "total":   "TOTAL CHANGE"}

def getcolour(cmd):
  if COLOR:
    return subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT).decode("utf-8")
  else:
    return ""

COLOURS = {"red": getcolour("tput setaf 1 bold"),
           "yellow": getcolour("tput setaf 3 bold"),
           "magenta": getcolour("tput setaf 5 bold"),
           "reset": getcolour("tput sgr0") }

TX_WARNING = "red"
TX_KERNEL = "magenta"
TX_SONAME = "yellow"

def printerr(msg, end="\n"):
  print(msg, file=sys.stderr, end=end)
  sys.stderr.flush()

def colour(acolour, text):
  return "%s%s%s" % (COLOURS[acolour], text, COLOURS["reset"])

def loadfile(filename):
  with codecs.open(filename, "rb", encoding="utf-8") as i:
    return parsedata(i.read())

#-rw-r--r-- 1 root root    1722 2017-08-24 22:03:23.000000000 +0100 ./etc/avahi/avahi-daemon.conf
def parsedata(data):
  newdata = []
  for line in data.split("\n"):
    fields = re_parse.split(line)

    if len(fields) == 11:
      fsize = int(fields[5])
      fname = fields[9][1:]

      altname = fname
      colourname = None
      so_count = 0
      so_version = ""
      is_kernel = False

      for so_match in [re_soname3, re_soname2, re_soname1, re_sonameM]:
        temp = so_match.match(fname)
        if temp:
          altname = temp.groups(1)[0]
          so_version = temp.groups(1)[2]
          colourname = "%s%s%s" % (altname, temp.groups(1)[1], colour(TX_SONAME, so_version))
          if len(temp.groups(1)) == 4:
            altname += temp.groups(1)[3]
            colourname += temp.groups(1)[3]
          so_count = so_version.count(".") + 1
          break

      temp = re_kmodule.match(altname)
      if temp:
        kernel_version = temp.groups(1)[1]
        altname = temp.groups(1)[0] + temp.groups(1)[2]
        colourname = "%s%s%s" % (temp.groups(1)[0], colour(TX_KERNEL, kernel_version), temp.groups(1)[2])
      else:
        kernel_version = ""

      newdata.append({"size": fsize, "filename": fname, "altname": altname, "colour": colourname,
                      "soversion": so_version, "sotype": so_count, "kmversion": kernel_version})

  return newdata

def analyse(filename):
  kernel = ""
  data = loadfile(filename)

  for item in data:
    if item["kmversion"]:
      kernel = item["kmversion"]
      break

  nlookup = {}
  alookup = {}
  for item in data:
    nlookup[item["filename"]] = item
    alookup[item["altname"]] = item

  return {"kernel": kernel, "data": data, "nlookup": nlookup, "alookup": alookup}

def sosearch(search, alist):
  for item in alist:
    data = alist[item]
    if data["soversion"]:
      if search["altname"] == data["altname"]:
        return data

  return None

def compare(data1, data2):
  global SONAME_WARNING

  results = []

  nlookup = data1["nlookup"]
  alookup = data1["alookup"]

  for item in data2["data"]:
    fsize = item["size"]
    fname = item["filename"]
    aname = item["altname"]

    # Lookup other list - second and third lookups are pre-/usr and post-/usr forms
    other = nlookup.get(fname, nlookup.get("/usr/%s" % fname, nlookup.get(fname[4:], None)))

    if not other and item["soversion"]:
      other = sosearch(item, nlookup)

    # If not found, use alternative name (unversioned kernel module name, unversioned soname, etc.)
    if other is None:
      if (item["kmversion"] and MAPKERNEL) or (item["soversion"] and MAPSONAME):
        other = alookup.get(aname, alookup.get("/usr/%s" % aname, alookup.get(aname[4:], None)))

    if other is None:
      if NONEW == False:
        results.append({"type": "new", "delta": fsize, "item1": None, "item2": item})
    else:
      osize = other["size"]
      if fsize != osize:
        results.append({"type": "size", "delta": (fsize - osize), "item1": other, "item2": item})
      elif item["soversion"] != other["soversion"]:
        results.append({"type": "soname", "delta": (fsize - osize), "item1": other, "item2": item})

      if item["soversion"] != other["soversion"]:
        SONAME_WARNING = True

  if MISSING:
    nlookup = data2["nlookup"]
    alookup = data2["alookup"]

    for item in data1["data"]:
      fsize = item["size"]
      fname = item["filename"]
      aname = item["altname"]

      # Lookup other list - second and third lookups are pre-/usr and post-/usr forms
      other = nlookup.get(fname, nlookup.get("/usr/%s" % fname, nlookup.get(fname[4:], None)))

      if not other and item["soversion"]:
        other = sosearch(item, nlookup)

      # If not found, use alternative name (unversioned kernel module name, unversioned soname, etc.)
      if other is None:
        if (item["kmversion"] and MAPKERNEL) or (item["soversion"] and MAPSONAME):
          other = alookup.get(aname, alookup.get("/usr/%s" % aname, alookup.get(aname[4:], None)))

      if other is None:
        results.append({"type": "missing", "delta": (0 - fsize), "item1": None, "item2": item})

  if NAMESORT:
    return sorted(results, key=lambda item: (item["item2"]["filename"], item["delta"]))
  else:
    return sorted(results, key=lambda item: (item["delta"], item["item2"]["filename"]))

def dump(r, build1, build2, kernel1=None, kernel2=None):
  global BELOW_THRESHOLD

  type = r["type"]
  delta = r["delta"]
  udelta = abs(delta)

  if type != "total":
    item1 = r["item1"]
    item2 = r["item2"]

    if item2["soversion"] and item2["colour"]:
      fname = item2["colour"]
      if item1 and item1["soversion"] != item2["soversion"]:
        fname += " (%s SONAME: %s)" % (build1, colour(TX_SONAME, item1["soversion"]))
    elif item2["kmversion"] and item2["colour"]:
      fname = item2["colour"]
      if item1 and item1["kmversion"] != item2["kmversion"]:
        fname += " (%s KERNEL: %s)" % (build1, colour(TX_KERNEL, item1["kmversion"]))
    else:
      fname = item2["filename"]

  if type == "size" and (udelta == 0 or udelta <= MINDELTA) and item1["soversion"] == item2["soversion"]:
    BELOW_THRESHOLD += 1
    return

#  wmax = 5 if len(build2) < 5 else len(build2)
#  label = "%-14s %*s" % (LABELS[type], wmax, "Delta")
  label = "%-14s %s" % (LABELS[type], "Delta")

  if type == "total":
    msg = "%s: %s" % (label, format(delta, ",d"))
    msg += " (less) " if delta < 0 else " (more) "
    msg += "in %s (kernel %s) compared with %s (kernel %s) [minimum delta: %s, files below threshhold: %s]" % \
            (build2, kernel2, build1, kernel1, MINDELTA, BELOW_THRESHOLD)
  else:
    msg = "%s: %-13s" % (label, format(delta, ",d"))
    if type in ["size", "soname"]:
      msg += "%s: %-13s %s: %-13s" % (build2, format(item2["size"], ",d"), build1, format(item1["size"], ",d"))
    elif type == "new":
      msg += "%s: %-13s %s: %-13s" % (build2, format(item2["size"], ",d"), build1, "n/a")
    elif type == "missing":
      msg += "%s: %-13s %s: %-13s" % (build2, "n/a", build1, format(item2["size"], ",d"))
    msg += fname

  print(msg)

if len(sys.argv) != 5:
  printerr("Incorrect arguments!\n")
  sys.exit(1)

build1 = sys.argv[1]
build2 = sys.argv[2]

data1 = analyse(sys.argv[3])
data2 = analyse(sys.argv[4])

diff = compare(data1, data2)

tdelta = 0
for type in ["missing", "new", "kernel", "size", "soname"]:
  for r in [d for d in diff if d["type"] == type]:
    tdelta += r["delta"]
    dump(r, build1, build2)

dump({"type": "total", "delta": tdelta}, build1, build2, data1["kernel"], data2["kernel"])

#if SONAME_WARNING and MINDELTA > 0:
#  print("")
#  print("%s (if not listed, below threshold or suppressed)" % colour(TX_WARNING, "** WARNING! ** SONAME CHANGES DETECTED! ** WARNING! **"))
