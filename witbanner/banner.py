from __future__ import print_function

import sys
from builtins import input

from future.standard_library import install_aliases
install_aliases()
from urllib.parse import urlparse, urlencode, urljoin, parse_qs

import requests

from bs4 import BeautifulSoup

import getpass

##############################################################################
##############################################################################

_BASE_URL = "https://prodweb2.wit.edu"
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL'
_SID = None

def _call(endpoint, method, params):
	global _SID
	if _SID is None:
		return False, None

	r = getattr(requests,method)(urljoin(_BASE_URL, endpoint), cookies={"SESSID":_SID}, data=params)
	if "SESSID" in r.cookies:
		_SID = r.cookies["SESSID"]
		return True, r
	else:
		_SID = None
		return False, r

def _get(endpoint, params={}):
	return _call(endpoint, "get", params)

def _post(endpoint, params={}):
	return _call(endpoint, "post", params)

def init(sid=None, u=None, p=None):
	global _SID

	if sid is None:
		baseurl = "https://cas.wit.edu"
		endpoint = "/cas/login?"
		service = "https://prodweb2.wit.edu:443/ssomanager/c/SSB"
		query_string = urlencode({"service":service})
		url = (baseurl + endpoint + query_string)

		soup = BeautifulSoup(requests.get(url).text, "html.parser")

		f = soup.find("form")

		action = baseurl + f["action"]
		params = {}

		for input_field in f.find_all("input", {"type":"hidden"}):
			params[safestr(input_field["name"])] = safestr(input_field["value"])

		##

		params["username"] = input("Login: ") if u is None else u
		params["password"] = getpass.getpass("Password: ") if p is None else p

		r = requests.post(action, data=params)
		if "SESSID" in r.cookies:
			_SID = r.cookies["SESSID"]
			return True
	else:
		_SID = sid
		if mainmenu() is None:
			_SID = None
			return False
		else:
			return True

def lastid():
	global _SID
	return _SID

##############################################################################
##############################################################################

def safestr(s):
	try:
		return unicode(s)
	except Exception:
		return str(s)

##############################################################################
##############################################################################

# necessary hack because banner doesn't properly close tags
# seems to have been fixed!
# def _getstring(tag):
# 	firstline = safestr(tag).splitlines()[0]
# 	return firstline[firstline.find(">")+1:].strip()

def _parse_select(select):
	# return {safestr(option["value"]):_getstring(option) for option in select.find_all("option")}
	return {safestr(option["value"]):safestr(option.string).strip() for option in select.find_all("option")}

##############################################################################
##############################################################################

def _parse_menu(html):
	retval = { "links":{} }
	soup = BeautifulSoup(html, "html.parser")

	retval["title"] = safestr(soup.title.string)

	maintable = soup.find("table", {"class":"menuplaintable"})
	for link in maintable.find_all("a", {"class":"submenulinktext2"}):
		retval["links"][safestr(link.string)] = safestr(link["href"])

	return retval


def _parse_form(html):
	retval = { "params":{} }
	soup = BeautifulSoup(html, "html.parser")

	retval["title"] = safestr(soup.title.string)

	form = soup.find("div", {"class":"pagebodydiv"}).find("form")

	retval["action"] = safestr(form["action"])

	for select in form.find_all("select"):
		retval["params"][safestr(select["name"])] = _parse_select(select)

	for hidden in form.find_all("input", {"type":"hidden"}):
		retval["params"][safestr(hidden["name"])] = safestr(hidden["value"])

	return retval


def _parse_summaryclasslist(html):
	retval = []
	soup = BeautifulSoup(html, "html.parser")

	# 0=course information, 1=enrollment counts
	infotable = soup.find_all("table", {"class":"datadisplaytable"})[2]
	for student in infotable.find_all("tr")[1:]:
		info = {}
		fields = student.find_all("td")

		info["wid"] = safestr(fields[2].span.string)
		if (fields[1].span.find("a") is None):
			info["deceased"] = True
			info["name_lastfirst"] = safestr(fields[1].span.contents[0].strip())
		else:
			info["deceased"] = False
			info["name_lastfirst"] = safestr(fields[1].span.a.string)
		info["name_firstfirst"] = safestr(fields[-2].span.a["target"])
		info["email"] = safestr(fields[-2].span.a["href"].split(":")[1])
		info["img"] = safestr(fields[-1].img["src"])

		retval.append(info)

	return retval


def _parse_detailclasslist(html):
	retval = []
	soup = BeautifulSoup(html, "html.parser")

	# 0=course information, 1=enrollment counts
	infotable = soup.find_all("table", {"class":"datadisplaytable"})[2]
	rowstate = 1
	info = {}
	for row in infotable.find_all("tr")[1:]:
		if rowstate is 1:
			fields = row.find_all("td")
			info["wid"] = safestr(fields[2].string)
			if (fields[1].find("a") is None):
				info["deceased"] = True
				info["name_lastfirst"] = safestr(fields[1].contents[0].strip())
			else:
				info["deceased"] = False
				info["name_lastfirst"] = safestr(fields[1].a.string)
			info["email"] = safestr(fields[5].span.a["href"].split(":")[1])
			rowstate+=1
			continue
		elif rowstate in [2, 3, 4]:
			rowstate+=1
			continue
		elif rowstate in [5, 6]:
			if row.find("th") is None:
				rowstate+=1
			else:
				info[safestr(row.th.string.split(":")[0])] = safestr(row.td.string).strip()
		elif rowstate is 7:
			rowstate = 1
			retval.append(info)
			info = {}
			continue

	# don't forget the last student!
	retval.append(info)

	return retval


def _parse_courselist(html):
	retval = []
	soup = BeautifulSoup(html, "html.parser")

	for course in soup.find_all("form", {"action":"/SSBPROD/bwskfcls.P_GetCrse"}):
		info = {
			"subj":safestr(course.find("input", {"name":"sel_subj", "value":lambda x: x!="dummy"})["value"]),
			"num":safestr(course.find("input", {"name":"SEL_CRSE"})["value"]),
			"title":safestr(course.parent.find_previous_sibling("td").string),
		}
		retval.append(info)

	return retval


def _parse_searchform(html):
	soup = BeautifulSoup(html, "html.parser")
	selects = {
		"sel_subj":"subjects",
		"sel_schd":"schedules",
		"sel_levl":"levels",
		"sel_ptrm":"parts",
		"sel_instr":"instructors",
	}

	return {key:_parse_select(soup.find("select", {"name":name})) for name,key in selects.items()}


def _parse_sectionlist(html):
	retval = []
	soup = BeautifulSoup(html, "html.parser")

	maintable = soup.find("table", {"class":"datadisplaytable"})

	if maintable is not None:
		state = 1
		for row in maintable.find_all("tr"):
			if state is 1:
				state+=1
				continue
			elif state is 2:
				state+=1
				continue
			elif state is 3:
				cols = row.find_all("td")
				if len(cols) is 0:
					state = 2
				else:
					if cols[1].find("a") is not None:
						course = {}
						course["crn"] = safestr(cols[1].a.string)
						course["status"] = safestr(cols[0].string)
						course["subj"] = safestr(cols[2].string)
						course["num"] = safestr(cols[3].string)
						course["section"] = safestr(cols[4].string)
						course["credits"] = safestr(cols[6].string)
						course["title"] = safestr(cols[7].string)
						course["cap"] = safestr(cols[10].string)
						course["active"] = safestr(cols[11].string)
						course["attr"] = safestr(cols[16].string.strip())
						course["instructor"] = ' '.join(safestr(''.join([s for s in cols[13].stripped_strings])).split())
						course["class"] = [(safestr(cols[8].string),safestr(cols[9].string),safestr(cols[15].string))]

						retval.append(course)
					else:
						retval[len(retval)-1]["class"].append((safestr(cols[8].string),safestr(cols[9].string),safestr(cols[15].string)))

				continue

	return retval


def _parse_adviseelisting(html):
	retval = []
	soup = BeautifulSoup(html, "html.parser")

	maintable = soup.find("table", {"class":"datadisplaytable"})
	for student in maintable.find_all("tr")[1:-2]:
		fields = student.find_all("td")

		info = {}
		info["name_lastfirst"] = safestr(fields[0].span.a.string)
		info["xyz"] = safestr(parse_qs(urlparse(fields[0].span.a["href"]).query)[u"xyz"][0])
		info["wid"] = safestr(fields[1].contents[0]).strip()
		info["name_firstfirst"] = safestr(fields[1].a["target"])
		info["email"] = safestr(fields[1].a["href"].split(":")[1])

		pin = fields[3].string.strip()
		if len(pin) is not 0:
			info["pin"] = safestr(pin)

		info["img"] = safestr(fields[9].img["src"])

		retval.append(info)

	return retval


def _parse_verifyxyz(html):
	soup = BeautifulSoup(html, "html.parser")

	result = soup.find_all("form")[1].find("input", {"name":"xyz"})
	if result is None:
		return None
	else:
		return safestr(result["value"])

# many options crashes bs4 due to bad option html
def _parse_choosexyz(html):
	retval = {}
	for opt in [safestr(line) for line in html.splitlines() if line.find("<OPTION VALUE=") is 0]:
		xyz = opt.split("\"")[1]
		v = opt[opt.find(">")+1:]
		val = v[:v.rfind(" ")].strip(),v[v.rfind(" ")+1:]
		retval[xyz] = val

	if not retval:
		return None
	else:
		return retval

def _parse_studentschedule(html):
	retval = []
	soup = BeautifulSoup(html, "html.parser")

	datatables = soup.find_all("table", {"class":"datadisplaytable"})
	entry = None
	for datatable in datatables:
		if datatable.has_attr("summary"):
			if "schedule course detail" in datatable["summary"]:
				if entry is not None and "meetings" not in entry:
					entry["meetings"] = []
					retval.append(entry)
				
				entry = {"title":safestr(datatable.caption.string)}

				for row in datatable.find_all("tr"):
					acr = row.th.find("acronym")
					if acr:
						k = safestr(row.th.acronym.string)
					else:
						k = safestr(row.th.string)[:-1]

					links = row.td.find_all("a")
					if links:
						v = [{"name":safestr(a["target"]), "email":safestr(a["href"].split(":")[1])} for a in links]
					else:
						v = safestr(row.td.string).strip()
					entry[k] = v
			elif "scheduled meeting times" in datatable["summary"]:
				meetings = []
				for row in datatable.find_all("tr")[1:]:
					cols = row.find_all("td")
					if not cols[1].abbr:
						meetings.append({"type":safestr(cols[5].string), "days":list(safestr(cols[2].string)), "times":safestr(cols[1].string).split(" - ")})
				entry["meetings"] = meetings
				retval.append(entry)

	return retval

# Student Information...
# - "info": {
#   - "Birth Date": [ "" ]
#   - "College": [ "" ]
#   - "Major and Department": [ "" ]
#   - "Minor": [ "" ]
#   - "Name": [ "" ]
#   - "Program": [ "" ]
#   - "Student Type": [ "" ]
# }
#
# Current Courses...
# - "current": {
#   - "term": ""
#   - "courses": [
#     - "course": ""
#     - "credits": #
#     - "level": ""
#     - "subject": ""
#     - "title": ""
#   ]
# }
#
# Institutional Credit...
# - "terms": [{
#   - "Academic Standing": ""
#   - "Major": ""
#   - "Student Type": ""
#   - "term": ""
#   - "courses": [{
#     - "course": ""
#     - "credits": #
#     - "grade": ""
#     - "level": ""
#     - "quality": #
#     - "subject": ""
#     - "title": ""
#   }]
#   - "cumulative"/"current": {
#     - "gpa": #
#     - "h_attempted": #
#     - "h_earned": #
#     - "h_gpa": #
#     - "h_passed": #
#     - "p_quality": #
#   }
# }]
#
# Transfer Credit...
# - "transfer": [{
#   - "source": ""
#   - "term": ""
#   - "credits": [{
#     - "course": ""
#     - "credits": #
#     - "subject": ""
#     - "title": ""
#   }]
# }]
#
# Totals...
# - "totals": {
#   - "inst"/"transfer"/"overall": {
#     - "gpa": #
#     - "h_attempted": #
#     - "h_earned": #
#     - "h_gpa": #
#     - "h_passed": #
#     - "p_quality": #
#   }
# }
def _parse_studenttranscript(html):
	retval = {
		"info": {},
		"transfer":[],
		"terms":[],
		"totals":{},
		"current": {
			"courses":[],
		}
	}
	soup = BeautifulSoup(html, "html.parser")

	maintable = soup.find("table", {"class":"datadisplaytable"})

	STUD_INFO = (0,1,2,)
	TRANSFER = "TRANSFER CREDIT ACCEPTED BY INSTITUTION"
	INST = "INSTITUTION CREDIT"
	TERM_TOTAL = "Term Totals (Undergraduate)"
	INST_TOTAL = "TRANSCRIPT TOTALS (UNDERGRADUATE)"
	PROGRESS = "COURSES IN PROGRESS"

	phase = 0
	stuff = None
	for row in maintable.find_all("tr"):
		if row.find("th", {"class":"ddtitle",}):
			if phase in STUD_INFO:
				phase += 1

			if phase not in STUD_INFO:
				phase = row.find("th", {"class":"ddtitle",}).find(text=True, recursive=False).strip()

		if phase in STUD_INFO:
			title = row.find("th", {"class":"ddlabel"})
			if title:
				value = row.find("td", {"class":"dddefault"})
				if value:
					key = safestr(title.text[:title.text.find(":")].strip())
					value = safestr(value.text)
					if key in retval["info"]:
						retval["info"][key].append(value)
					else:
						retval["info"][key] = [value]

		if phase == TRANSFER:
			th = row.find_all("th")
			td = row.find_all("td")

			if len(th) is 1 and len(td) is 1:
				stuff = []
				retval["transfer"].append({
					"source":safestr(td[0].text),
					"term":safestr(th[0].text[:th[0].text.find(":")]),
					"credits":stuff
				})
			elif len(th) is 0 and len(td) is 7:
				subj = safestr(td[0].text)
				course = safestr(td[1].text)
				t = safestr(td[2].text)
				credits = float(td[4].text)
				stuff.append({
					"subject":subj,
					"course":course,
					"title":t,
					"credits":credits,
				})

		if phase == INST:
			th = row.find_all("th")
			td = row.find_all("td")

			if row.find("span", {"class":"fieldOrangetextbold",}):
				stuff = {
					"term":safestr(row.text[row.text.find(":")+1:].strip()),
					"courses":[],
				}
				retval["terms"].append(stuff)
			elif len(th) is 1 and len(td) is 1:
				key = safestr(th[0].text.strip())
				val = safestr(td[0].text.strip())
				stuff[key] = val
			elif len(th) is 0 and len(td) is 10:
				subj = safestr(td[0].text)
				course = safestr(td[1].text)
				level = safestr(td[2].text)
				t = safestr(td[3].text)
				grade = safestr(td[4].text)
				credits = float(td[5].text)
				quality = float(td[6].text)
				stuff["courses"].append({
					"subject":subj,
					"course":course,
					"level":level,
					"title":t,
					"grade":grade,
					"credits":credits,
					"quality":quality,
				})

		if phase == TERM_TOTAL:
			if row.find("td", {"class":"ddseparator"}):
				phase = INST
			else:
				th = row.find_all("th")
				td = row.find_all("td")

				if len(th) is 1 and len(td) is 6:
					result_type = th[0].text
					if result_type == "Current Term:":
						result_type = "current"
					else:
						result_type = "cumulative"

					stuff[result_type] = {
						"h_attempted":float(td[0].text.strip()),
						"h_passed":float(td[1].text.strip()),
						"h_earned":float(td[2].text.strip()),
						"h_gpa":float(td[3].text.strip()),
						"p_quality":float(td[4].text.strip()),
						"gpa":float(td[5].text.strip()),
					}

		if phase == INST_TOTAL:
			th = row.find_all("th")
			td = row.find_all("td")

			if len(th) is 1 and len(td) is 6:
				result_type = th[0].text

				if result_type == "Total Institution:":
					result_type = "inst"
				elif result_type == "Total Transfer:":
					result_type = "transfer"
				else:
					result_type = "overall"

				retval["totals"][result_type] = {
					"h_attempted":float(td[0].p.text.strip()),
					"h_passed":float(td[1].p.text.strip()),
					"h_earned":float(td[2].p.text.strip()),
					"h_gpa":float(td[3].p.text.strip()),
					"p_quality":float(td[4].p.text.strip()),
					"gpa":float(td[5].p.text.strip()),
				}

		if phase == PROGRESS:
			th = row.find_all("th")
			td = row.find_all("td")

			if row.find("span", {"class":"fieldOrangetextbold",}):
				retval["current"]["term"] = safestr(row.text[row.text.find(":")+1:].strip())

			if len(th) is 0 and len(td) is 5:
				subj = safestr(td[0].text)
				course = safestr(td[1].text)
				level = safestr(td[2].text)
				t = safestr(td[3].text)
				credits = float(td[4].text)

				retval["current"]["courses"].append({
					"subject":subj,
					"course":course,
					"level":level,
					"title":t,
					"credits":credits,
				})

	return retval

def _parse_studenttestscore(html):
	retval = {}
	soup = BeautifulSoup(html, "html.parser")

	maintable = soup.find("table", {"class":"datadisplaytable"})
	if maintable:
		rows = maintable.find_all("tr")[1:]
		for row in rows:
			cols = row.find_all("td")
			testname = safestr(cols[0].text)
			testscore = safestr(cols[1].text)
			testdate = safestr(cols[2].text)

			if testname not in retval:
				retval[testname] = []
			retval[testname].append((testscore, testdate,))				

	return retval

##############################################################################
##############################################################################

def mainmenu():
	good,r = _get("/SSBPROD/twbkwbis.P_GenMenu?name=bmenu.P_MainMnu")
	if good:
		return _parse_menu(r.text)
	else:
		return None

def facultymenu():
	good,r = _get("/SSBPROD/twbkwbis.P_GenMenu?name=bmenu.P_FacMainMnu")
	if good:
		return _parse_menu(r.text)
	else:
		return None

def termform():
	good,r = _get("/SSBPROD/bwlkostm.P_FacSelTerm")
	if good:
		return _parse_form(r.text)
	else:
		return None

def termset(term):
	good,r = _post("/SSBPROD/bwlkostm.P_FacStoreTerm", {"term":term, "name1":"bmenu.P_FacMainMnu"})
	if good:
		return term
	else:
		return None

def crnform():
	good,r = _get("/SSBPROD/bwlkocrn.P_FacCrnSel")
	if good:
		return _parse_form(r.text)
	else:
		return None

def crnset(crn):
	# unsure if calling_proc should be P_FACENTERCRN or P_FACCRNSEL, but I'm guessing the former is more flexible
	good,r = _post("/SSBPROD/bwlkocrn.P_FacStoreCRN", {"crn":crn, "name1":"bmenu.P_FacMainMnu", "calling_proc_name":"P_FACENTERCRN"})
	if good:
		return crn
	else:
		return None

def summaryclasslist():
	good,r = _get("/SSBPROD/bwlkfcwl.P_FacClaListSum")
	if good:
		return _parse_summaryclasslist(r.text)
	else:
		return None

def detailclasslist():
	good,r = _get("/SSBPROD/bwlkfcwl.P_FacClaList")
	if good:
		return _parse_detailclasslist(r.text)
	else:
		return None

def sectiontermform():
	good,r = _get("/SSBPROD/bwskfcls.p_sel_crse_search")
	if good:
		return _parse_form(r.text)
	else:
		return None

# not sure if this is ever going to be useful... (just sets the term_in in searches)
def sectiontermset(term):
	good,r = _post("/SSBPROD/bwckgens.p_proc_term_date", {"p_term":term, "p_calling_proc":"P_CrseSearch"})
	if good:
		return term
	else:
		return None

def coursesearch(term, subjects):
	params = [
		("sel_subj","dummy"),
		("path","1"),
		("rsts","dummy"),
		("crn","dummy"),
		("sel_day","dummy"),
		("sel_schd","dummy"),
		("sel_insm","dummy"),
		("sel_camp","dummy"),
		("sel_levl","dummy"),
		("sel_sess","dummy"),
		("sel_instr","dummy"),
		("sel_ptrm","dummy"),
		("sel_attr","dummy"),
		("begin_ap","x"),
		("end_ap","y"),
		("SUB_BTN","Course Search"),
		("sel_crse",""),
		("sel_title",""),
		("sel_from_cred",""),
		("sel_to_cred",""),
		("sel_ptrm","%"),
		("begin_hh","0"),
		("begin_mi","0"),
		("end_hh","0"),
		("end_mi","0")
	]

	params.append(("term_in",term))
	for subj in subjects:
		params.append(("sel_subj", subj))

	good,r = _post("/SSBPROD/bwskfcls.P_GetCrse", params)
	if good:
		return _parse_courselist(r.text)
	else:
		return None

def sectioncodes(term):
	params = [
		("sel_subj","dummy"),
		("path","1"),
		("rsts","dummy"),
		("crn","dummy"),
		("sel_day","dummy"),
		("sel_schd","dummy"),
		("sel_insm","dummy"),
		("sel_camp","dummy"),
		("sel_levl","dummy"),
		("sel_sess","dummy"),
		("sel_instr","dummy"),
		("sel_ptrm","dummy"),
		("sel_attr","dummy"),
		("begin_ap","x"),
		("end_ap","y"),
		("SUB_BTN","Advanced Search"),
		("sel_crse",""),
		("sel_title",""),
		("sel_from_cred",""),
		("sel_to_cred",""),
		("sel_ptrm","%"),
		("begin_hh","0"),
		("begin_mi","0"),
		("end_hh","0"),
		("end_mi","0")
	]

	params.append(("term_in",term))

	good,r = _post("/SSBPROD/bwskfcls.P_GetCrse", params)
	if good:
		return _parse_searchform(r.text)
	else:
		return None

def sectionsearch(term, subjects, num="", title="", schedules=["%"], cred_from="", cred_to="", levels=["%"], partsofterm=["%"], instructors=["%"], attrs=["%"], beginh="0", beginm="0", beginap="a", endh="0", endm="0", endap="a", days=[]):
	params = [
		("rsts","dummy"),
		("crn","dummy"),
		("sel_subj","dummy"),
		("sel_day","dummy"),
		("sel_schd","dummy"),
		("sel_insm","dummy"),
		("sel_camp","dummy"),
		("sel_levl","dummy"),
		("sel_sess","dummy"),
		("sel_instr","dummy"),
		("sel_ptrm","dummy"),
		("sel_attr","dummy"),
		("sel_crse",num),
		("sel_title",title),
		("sel_from_cred",cred_from),
		("sel_to_cred",cred_to),
		("begin_hh", beginh),
		("begin_mi", beginm),
		("begin_ap", beginap),
		("end_hh", endh),
		("end_mi", endm),
		("end_ap", endap),
		("SUB_BTN","Advanced Search"),
		("path","1"),
	]

	params.append(("term_in",term))

	to_add = {
		"sel_subj":subjects,
		"sel_schd":schedules,
		"sel_levl":levels,
		"sel_ptrm":partsofterm,
		"sel_instr":instructors,
		"sel_attr":attrs,
		"sel_day":days,
	}

	for key,source in to_add.items():
		for s in source:
			params.append((key, s))

	good,r = _post("/SSBPROD/bwskfcls.P_GetCrse_Advanced", params)
	if good:
		return _parse_sectionlist(r.text)
	else:
		return None

def adviseelisting():
	good,r = _get("/SSBPROD/bwlkadvr.P_DispAdvisees")
	if good:
		return _parse_adviseelisting(r.text)
	else:
		return None

def getxyz_wid(term, wid):
	params = {
		"TERM":term,
		"CALLING_PROC_NAME":"",
		"CALLING_PROC_NAME2":"",
		"term_in":"",
		"STUD_ID":wid,
		"last_name":"",
		"first_name":"",
		"search_type":"All", # Stu, Adv, Both, All
	}

	good,r = _post("/SSBPROD/bwlkoids.P_FacVerifyID", params)
	if good:
		return _parse_verifyxyz(r.text)
	else:
		return None

def getxyz_name(term, first="", last="", stype="All"):
	params = {
		"TERM":term,
		"CALLING_PROC_NAME":"",
		"CALLING_PROC_NAME2":"",
		"term_in":"",
		"STUD_ID":"",
		"last_name":last, # %
		"first_name":first, # %
		"search_type":stype, # Stu, Adv, Both, All
	}

	good,r = _post("/SSBPROD/bwlkoids.P_FacVerifyID", params)
	if good:
		return _parse_choosexyz(r.text)
	else:
		return None

def idset(xyz):
	params = {
		"term_in":"",
		"sname":"bmenu.P_FacStuMnu",
		"xyz":xyz,
	}

	good,r = _post("/SSBPROD/bwlkoids.P_FacStoreID", params)
	if good:
		return xyz
	else:
		return None

def studentschedule():
	good,r = _get("/SSBPROD/bwlkfstu.P_FacStuSchd")
	if good:
		return _parse_studentschedule(r.text)
	else:
		return None

def studenttranscript():
	params = {
		"levl":"",
		"tprt":"WEB",
	}

	good,r = _post("/SSBPROD/bwlkftrn.P_ViewTran", params)
	if good:
		return _parse_studenttranscript(r.text)
	else:
		return None

def studenttestscores():
	good,r = _get("/SSBPROD/bwlktest.P_FacDispTest")
	if good:
		return _parse_studenttestscore(r.text)
	else:
		return None
