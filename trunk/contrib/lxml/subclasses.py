#!/usr/bin/env python

#
# Generated Fri Jun 22 13:30:40 2012 by generateDS.py version 2.7b.
#

import sys

import ??? as supermod

etree_ = None
Verbose_import_ = False
(   XMLParser_import_none, XMLParser_import_lxml,
    XMLParser_import_elementtree
    ) = range(3)
XMLParser_import_library = None
try:
    # lxml
    from lxml import etree as etree_
    XMLParser_import_library = XMLParser_import_lxml
    if Verbose_import_:
        print("running with lxml.etree")
except ImportError:
    try:
        # cElementTree from Python 2.5+
        import xml.etree.cElementTree as etree_
        XMLParser_import_library = XMLParser_import_elementtree
        if Verbose_import_:
            print("running with cElementTree on Python 2.5+")
    except ImportError:
        try:
            # ElementTree from Python 2.5+
            import xml.etree.ElementTree as etree_
            XMLParser_import_library = XMLParser_import_elementtree
            if Verbose_import_:
                print("running with ElementTree on Python 2.5+")
        except ImportError:
            try:
                # normal cElementTree install
                import cElementTree as etree_
                XMLParser_import_library = XMLParser_import_elementtree
                if Verbose_import_:
                    print("running with cElementTree")
            except ImportError:
                try:
                    # normal ElementTree install
                    import elementtree.ElementTree as etree_
                    XMLParser_import_library = XMLParser_import_elementtree
                    if Verbose_import_:
                        print("running with ElementTree")
                except ImportError:
                    raise ImportError("Failed to import ElementTree from any known place")

def parsexml_(*args, **kwargs):
    if (XMLParser_import_library == XMLParser_import_lxml and
        'parser' not in kwargs):
        # Use the lxml ElementTree compatible parser so that, e.g.,
        #   we ignore comments.
        kwargs['parser'] = etree_.ETCompatXMLParser()
    doc = etree_.parse(*args, **kwargs)
    return doc

#
# Globals
#

ExternalEncoding = 'utf-8'

#
# Data representation classes
#

class databaseSub(supermod.database):
    def __init__(self, xmlns=None, header=None, name_formats=None, tags=None, events=None, people=None, families=None, citations=None, sources=None, places=None, objects=None, repositories=None, notes=None, bookmarks=None, namemaps=None):
        super(databaseSub, self).__init__(xmlns, header, name_formats, tags, events, people, families, citations, sources, places, objects, repositories, notes, bookmarks, namemaps, )
supermod.database.subclass = databaseSub
# end class databaseSub


class headerSub(supermod.header):
    def __init__(self, created=None, researcher=None, mediapath=None):
        super(headerSub, self).__init__(created, researcher, mediapath, )
supermod.header.subclass = headerSub
# end class headerSub


class createdSub(supermod.created):
    def __init__(self, date=None, version=None):
        super(createdSub, self).__init__(date, version, )
supermod.created.subclass = createdSub
# end class createdSub


class researcherSub(supermod.researcher):
    def __init__(self, resname=None, resaddr=None, reslocality=None, rescity=None, resstate=None, rescountry=None, respostal=None, resphone=None, resemail=None):
        super(researcherSub, self).__init__(resname, resaddr, reslocality, rescity, resstate, rescountry, respostal, resphone, resemail, )
supermod.researcher.subclass = researcherSub
# end class researcherSub


class resnameSub(supermod.resname):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(resnameSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.resname.subclass = resnameSub
# end class resnameSub


class resaddrSub(supermod.resaddr):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(resaddrSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.resaddr.subclass = resaddrSub
# end class resaddrSub


class reslocalitySub(supermod.reslocality):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(reslocalitySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.reslocality.subclass = reslocalitySub
# end class reslocalitySub


class rescitySub(supermod.rescity):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(rescitySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.rescity.subclass = rescitySub
# end class rescitySub


class resstateSub(supermod.resstate):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(resstateSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.resstate.subclass = resstateSub
# end class resstateSub


class rescountrySub(supermod.rescountry):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(rescountrySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.rescountry.subclass = rescountrySub
# end class rescountrySub


class respostalSub(supermod.respostal):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(respostalSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.respostal.subclass = respostalSub
# end class respostalSub


class resphoneSub(supermod.resphone):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(resphoneSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.resphone.subclass = resphoneSub
# end class resphoneSub


class resemailSub(supermod.resemail):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(resemailSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.resemail.subclass = resemailSub
# end class resemailSub


class mediapathSub(supermod.mediapath):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(mediapathSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.mediapath.subclass = mediapathSub
# end class mediapathSub


class peopleSub(supermod.people):
    def __init__(self, default=None, home=None, person=None):
        super(peopleSub, self).__init__(default, home, person, )
supermod.people.subclass = peopleSub
# end class peopleSub


class personSub(supermod.person):
    def __init__(self, handle=None, id=None, change=None, priv=None, gender=None, name=None, eventref=None, lds_ord=None, objref=None, address=None, attribute=None, url=None, childof=None, parentin=None, personref=None, noteref=None, citationref=None, tagref=None):
        super(personSub, self).__init__(handle, id, change, priv, gender, name, eventref, lds_ord, objref, address, attribute, url, childof, parentin, personref, noteref, citationref, tagref, )
supermod.person.subclass = personSub
# end class personSub


class genderSub(supermod.gender):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(genderSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.gender.subclass = genderSub
# end class genderSub


class nameSub(supermod.name):
    def __init__(self, sort=None, alt=None, type_=None, display=None, priv=None, first=None, call=None, surname=None, suffix=None, title=None, nick=None, familynick=None, group=None, daterange=None, datespan=None, dateval=None, datestr=None, noteref=None, citationref=None):
        super(nameSub, self).__init__(sort, alt, type_, display, priv, first, call, surname, suffix, title, nick, familynick, group, daterange, datespan, dateval, datestr, noteref, citationref, )
supermod.name.subclass = nameSub
# end class nameSub


class firstSub(supermod.first):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(firstSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.first.subclass = firstSub
# end class firstSub


class callSub(supermod.call):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(callSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.call.subclass = callSub
# end class callSub


class suffixSub(supermod.suffix):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(suffixSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.suffix.subclass = suffixSub
# end class suffixSub


class titleSub(supermod.title):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(titleSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.title.subclass = titleSub
# end class titleSub


class nickSub(supermod.nick):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(nickSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.nick.subclass = nickSub
# end class nickSub


class familynickSub(supermod.familynick):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(familynickSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.familynick.subclass = familynickSub
# end class familynickSub


class groupSub(supermod.group):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(groupSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.group.subclass = groupSub
# end class groupSub


class surnameSub(supermod.surname):
    def __init__(self, connector=None, prefix=None, prim=None, derivation=None, valueOf_=None, mixedclass_=None, content_=None):
        super(surnameSub, self).__init__(connector, prefix, prim, derivation, valueOf_, mixedclass_, content_, )
supermod.surname.subclass = surnameSub
# end class surnameSub


class childofSub(supermod.childof):
    def __init__(self, hlink=None):
        super(childofSub, self).__init__(hlink, )
supermod.childof.subclass = childofSub
# end class childofSub


class parentinSub(supermod.parentin):
    def __init__(self, hlink=None):
        super(parentinSub, self).__init__(hlink, )
supermod.parentin.subclass = parentinSub
# end class parentinSub


class personrefSub(supermod.personref):
    def __init__(self, hlink=None, rel=None, priv=None, citationref=None, noteref=None):
        super(personrefSub, self).__init__(hlink, rel, priv, citationref, noteref, )
supermod.personref.subclass = personrefSub
# end class personrefSub


class addressSub(supermod.address):
    def __init__(self, priv=None, daterange=None, datespan=None, dateval=None, datestr=None, street=None, locality=None, city=None, county=None, state=None, country=None, postal=None, phone=None, noteref=None, citationref=None):
        super(addressSub, self).__init__(priv, daterange, datespan, dateval, datestr, street, locality, city, county, state, country, postal, phone, noteref, citationref, )
supermod.address.subclass = addressSub
# end class addressSub


class streetSub(supermod.street):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(streetSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.street.subclass = streetSub
# end class streetSub


class localitySub(supermod.locality):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(localitySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.locality.subclass = localitySub
# end class localitySub


class citySub(supermod.city):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(citySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.city.subclass = citySub
# end class citySub


class countySub(supermod.county):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(countySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.county.subclass = countySub
# end class countySub


class stateSub(supermod.state):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(stateSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.state.subclass = stateSub
# end class stateSub


class countrySub(supermod.country):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(countrySub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.country.subclass = countrySub
# end class countrySub


class postalSub(supermod.postal):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(postalSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.postal.subclass = postalSub
# end class postalSub


class phoneSub(supermod.phone):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(phoneSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.phone.subclass = phoneSub
# end class phoneSub


class familiesSub(supermod.families):
    def __init__(self, family=None):
        super(familiesSub, self).__init__(family, )
supermod.families.subclass = familiesSub
# end class familiesSub


class familySub(supermod.family):
    def __init__(self, handle=None, id=None, change=None, priv=None, rel=None, father=None, mother=None, eventref=None, lds_ord=None, objref=None, childref=None, attribute=None, noteref=None, citationref=None, tagref=None):
        super(familySub, self).__init__(handle, id, change, priv, rel, father, mother, eventref, lds_ord, objref, childref, attribute, noteref, citationref, tagref, )
supermod.family.subclass = familySub
# end class familySub


class fatherSub(supermod.father):
    def __init__(self, hlink=None):
        super(fatherSub, self).__init__(hlink, )
supermod.father.subclass = fatherSub
# end class fatherSub


class motherSub(supermod.mother):
    def __init__(self, hlink=None):
        super(motherSub, self).__init__(hlink, )
supermod.mother.subclass = motherSub
# end class motherSub


class childrefSub(supermod.childref):
    def __init__(self, frel=None, hlink=None, mrel=None, priv=None, citationref=None, noteref=None):
        super(childrefSub, self).__init__(frel, hlink, mrel, priv, citationref, noteref, )
supermod.childref.subclass = childrefSub
# end class childrefSub


class type_Sub(supermod.type_):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(type_Sub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.type_.subclass = type_Sub
# end class type_Sub


class relSub(supermod.rel):
    def __init__(self, type_=None):
        super(relSub, self).__init__(type_, )
supermod.rel.subclass = relSub
# end class relSub


class eventsSub(supermod.events):
    def __init__(self, event=None):
        super(eventsSub, self).__init__(event, )
supermod.events.subclass = eventsSub
# end class eventsSub


class eventSub(supermod.event):
    def __init__(self, handle=None, id=None, change=None, priv=None, type_=None, daterange=None, datespan=None, dateval=None, datestr=None, place=None, cause=None, description=None, attribute=None, noteref=None, citationref=None, objref=None):
        super(eventSub, self).__init__(handle, id, change, priv, type_, daterange, datespan, dateval, datestr, place, cause, description, attribute, noteref, citationref, objref, )
supermod.event.subclass = eventSub
# end class eventSub


class sourcesSub(supermod.sources):
    def __init__(self, source=None):
        super(sourcesSub, self).__init__(source, )
supermod.sources.subclass = sourcesSub
# end class sourcesSub


class sourceSub(supermod.source):
    def __init__(self, handle=None, id=None, change=None, priv=None, stitle=None, sauthor=None, spubinfo=None, sabbrev=None, noteref=None, objref=None, data_item=None, reporef=None):
        super(sourceSub, self).__init__(handle, id, change, priv, stitle, sauthor, spubinfo, sabbrev, noteref, objref, data_item, reporef, )
supermod.source.subclass = sourceSub
# end class sourceSub


class stitleSub(supermod.stitle):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(stitleSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.stitle.subclass = stitleSub
# end class stitleSub


class sauthorSub(supermod.sauthor):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(sauthorSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.sauthor.subclass = sauthorSub
# end class sauthorSub


class spubinfoSub(supermod.spubinfo):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(spubinfoSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.spubinfo.subclass = spubinfoSub
# end class spubinfoSub


class sabbrevSub(supermod.sabbrev):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(sabbrevSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.sabbrev.subclass = sabbrevSub
# end class sabbrevSub


class placesSub(supermod.places):
    def __init__(self, placeobj=None):
        super(placesSub, self).__init__(placeobj, )
supermod.places.subclass = placesSub
# end class placesSub


class placeobjSub(supermod.placeobj):
    def __init__(self, handle=None, id=None, change=None, priv=None, ptitle=None, coord=None, location=None, objref=None, url=None, noteref=None, citationref=None):
        super(placeobjSub, self).__init__(handle, id, change, priv, ptitle, coord, location, objref, url, noteref, citationref, )
supermod.placeobj.subclass = placeobjSub
# end class placeobjSub


class ptitleSub(supermod.ptitle):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(ptitleSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.ptitle.subclass = ptitleSub
# end class ptitleSub


class coordSub(supermod.coord):
    def __init__(self, lat=None, long=None):
        super(coordSub, self).__init__(lat, long, )
supermod.coord.subclass = coordSub
# end class coordSub


class locationSub(supermod.location):
    def __init__(self, city=None, locality=None, parish=None, county=None, phone=None, state=None, street=None, country=None, postal=None):
        super(locationSub, self).__init__(city, locality, parish, county, phone, state, street, country, postal, )
supermod.location.subclass = locationSub
# end class locationSub


class objectsSub(supermod.objects):
    def __init__(self, object=None):
        super(objectsSub, self).__init__(object, )
supermod.objects.subclass = objectsSub
# end class objectsSub


class objectSub(supermod.object):
    def __init__(self, handle=None, id=None, change=None, priv=None, file=None, attribute=None, noteref=None, daterange=None, datespan=None, dateval=None, datestr=None, citationref=None, tagref=None):
        super(objectSub, self).__init__(handle, id, change, priv, file, attribute, noteref, daterange, datespan, dateval, datestr, citationref, tagref, )
supermod.object.subclass = objectSub
# end class objectSub


class fileSub(supermod.file):
    def __init__(self, src=None, mime=None, description=None):
        super(fileSub, self).__init__(src, mime, description, )
supermod.file.subclass = fileSub
# end class fileSub


class repositoriesSub(supermod.repositories):
    def __init__(self, repository=None):
        super(repositoriesSub, self).__init__(repository, )
supermod.repositories.subclass = repositoriesSub
# end class repositoriesSub


class repositorySub(supermod.repository):
    def __init__(self, handle=None, id=None, change=None, priv=None, rname=None, type_=None, address=None, url=None, noteref=None):
        super(repositorySub, self).__init__(handle, id, change, priv, rname, type_, address, url, noteref, )
supermod.repository.subclass = repositorySub
# end class repositorySub


class rnameSub(supermod.rname):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(rnameSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.rname.subclass = rnameSub
# end class rnameSub


class notesSub(supermod.notes):
    def __init__(self, note=None):
        super(notesSub, self).__init__(note, )
supermod.notes.subclass = notesSub
# end class notesSub


class noteSub(supermod.note):
    def __init__(self, handle=None, format=None, type_=None, id=None, change=None, priv=None, text=None, style=None, tagref=None):
        super(noteSub, self).__init__(handle, format, type_, id, change, priv, text, style, tagref, )
supermod.note.subclass = noteSub
# end class noteSub


class textSub(supermod.text):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(textSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.text.subclass = textSub
# end class textSub


class styleSub(supermod.style):
    def __init__(self, name=None, value=None, range=None):
        super(styleSub, self).__init__(name, value, range, )
supermod.style.subclass = styleSub
# end class styleSub


class rangeSub(supermod.range):
    def __init__(self, start=None, end=None):
        super(rangeSub, self).__init__(start, end, )
supermod.range.subclass = rangeSub
# end class rangeSub


class tagsSub(supermod.tags):
    def __init__(self, tag=None):
        super(tagsSub, self).__init__(tag, )
supermod.tags.subclass = tagsSub
# end class tagsSub


class tagSub(supermod.tag):
    def __init__(self, color=None, priority=None, handle=None, name=None, change=None):
        super(tagSub, self).__init__(color, priority, handle, name, change, )
supermod.tag.subclass = tagSub
# end class tagSub


class citationsSub(supermod.citations):
    def __init__(self, citation=None):
        super(citationsSub, self).__init__(citation, )
supermod.citations.subclass = citationsSub
# end class citationsSub


class citationSub(supermod.citation):
    def __init__(self, handle=None, id=None, change=None, priv=None, daterange=None, datespan=None, dateval=None, datestr=None, page=None, confidence=None, noteref=None, objref=None, data_item=None, sourceref=None):
        super(citationSub, self).__init__(handle, id, change, priv, daterange, datespan, dateval, datestr, page, confidence, noteref, objref, data_item, sourceref, )
supermod.citation.subclass = citationSub
# end class citationSub


class bookmarksSub(supermod.bookmarks):
    def __init__(self, bookmark=None):
        super(bookmarksSub, self).__init__(bookmark, )
supermod.bookmarks.subclass = bookmarksSub
# end class bookmarksSub


class bookmarkSub(supermod.bookmark):
    def __init__(self, target=None, hlink=None):
        super(bookmarkSub, self).__init__(target, hlink, )
supermod.bookmark.subclass = bookmarkSub
# end class bookmarkSub


class namemapsSub(supermod.namemaps):
    def __init__(self, map=None):
        super(namemapsSub, self).__init__(map, )
supermod.namemaps.subclass = namemapsSub
# end class namemapsSub


class mapSub(supermod.map):
    def __init__(self, type_=None, value=None, key=None):
        super(mapSub, self).__init__(type_, value, key, )
supermod.map.subclass = mapSub
# end class mapSub


class name_formatsSub(supermod.name_formats):
    def __init__(self, format=None):
        super(name_formatsSub, self).__init__(format, )
supermod.name_formats.subclass = name_formatsSub
# end class name_formatsSub


class formatSub(supermod.format):
    def __init__(self, active=None, number=None, fmt_str=None, name=None):
        super(formatSub, self).__init__(active, number, fmt_str, name, )
supermod.format.subclass = formatSub
# end class formatSub


class daterangeSub(supermod.daterange):
    def __init__(self, cformat=None, stop=None, dualdated=None, start=None, newyear=None, quality=None):
        super(daterangeSub, self).__init__(cformat, stop, dualdated, start, newyear, quality, )
supermod.daterange.subclass = daterangeSub
# end class daterangeSub


class datespanSub(supermod.datespan):
    def __init__(self, cformat=None, stop=None, dualdated=None, start=None, newyear=None, quality=None):
        super(datespanSub, self).__init__(cformat, stop, dualdated, start, newyear, quality, )
supermod.datespan.subclass = datespanSub
# end class datespanSub


class datevalSub(supermod.dateval):
    def __init__(self, cformat=None, val=None, type_=None, dualdated=None, newyear=None, quality=None):
        super(datevalSub, self).__init__(cformat, val, type_, dualdated, newyear, quality, )
supermod.dateval.subclass = datevalSub
# end class datevalSub


class datestrSub(supermod.datestr):
    def __init__(self, val=None):
        super(datestrSub, self).__init__(val, )
supermod.datestr.subclass = datestrSub
# end class datestrSub


class citationrefSub(supermod.citationref):
    def __init__(self, hlink=None):
        super(citationrefSub, self).__init__(hlink, )
supermod.citationref.subclass = citationrefSub
# end class citationrefSub


class sourcerefSub(supermod.sourceref):
    def __init__(self, hlink=None):
        super(sourcerefSub, self).__init__(hlink, )
supermod.sourceref.subclass = sourcerefSub
# end class sourcerefSub


class eventrefSub(supermod.eventref):
    def __init__(self, role=None, hlink=None, priv=None, attribute=None, noteref=None):
        super(eventrefSub, self).__init__(role, hlink, priv, attribute, noteref, )
supermod.eventref.subclass = eventrefSub
# end class eventrefSub


class reporefSub(supermod.reporef):
    def __init__(self, medium=None, callno=None, hlink=None, priv=None, noteref=None):
        super(reporefSub, self).__init__(medium, callno, hlink, priv, noteref, )
supermod.reporef.subclass = reporefSub
# end class reporefSub


class noterefSub(supermod.noteref):
    def __init__(self, hlink=None):
        super(noterefSub, self).__init__(hlink, )
supermod.noteref.subclass = noterefSub
# end class noterefSub


class tagrefSub(supermod.tagref):
    def __init__(self, hlink=None):
        super(tagrefSub, self).__init__(hlink, )
supermod.tagref.subclass = tagrefSub
# end class tagrefSub


class pageSub(supermod.page):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(pageSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.page.subclass = pageSub
# end class pageSub


class confidenceSub(supermod.confidence):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(confidenceSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.confidence.subclass = confidenceSub
# end class confidenceSub


class attributeSub(supermod.attribute):
    def __init__(self, type_=None, value=None, priv=None, citationref=None, noteref=None):
        super(attributeSub, self).__init__(type_, value, priv, citationref, noteref, )
supermod.attribute.subclass = attributeSub
# end class attributeSub


class placeSub(supermod.place):
    def __init__(self, hlink=None):
        super(placeSub, self).__init__(hlink, )
supermod.place.subclass = placeSub
# end class placeSub


class causeSub(supermod.cause):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(causeSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.cause.subclass = causeSub
# end class causeSub


class descriptionSub(supermod.description):
    def __init__(self, valueOf_=None, mixedclass_=None, content_=None):
        super(descriptionSub, self).__init__(valueOf_, mixedclass_, content_, )
supermod.description.subclass = descriptionSub
# end class descriptionSub


class urlSub(supermod.url):
    def __init__(self, href=None, type_=None, description=None, priv=None):
        super(urlSub, self).__init__(href, type_, description, priv, )
supermod.url.subclass = urlSub
# end class urlSub


class objrefSub(supermod.objref):
    def __init__(self, hlink=None, priv=None, region=None, attribute=None, citationref=None, noteref=None):
        super(objrefSub, self).__init__(hlink, priv, region, attribute, citationref, noteref, )
supermod.objref.subclass = objrefSub
# end class objrefSub


class regionSub(supermod.region):
    def __init__(self, corner1_x=None, corner1_y=None, corner2_y=None, corner2_x=None):
        super(regionSub, self).__init__(corner1_x, corner1_y, corner2_y, corner2_x, )
supermod.region.subclass = regionSub
# end class regionSub


class data_itemSub(supermod.data_item):
    def __init__(self, value=None, key=None):
        super(data_itemSub, self).__init__(value, key, )
supermod.data_item.subclass = data_itemSub
# end class data_itemSub


class lds_ordSub(supermod.lds_ord):
    def __init__(self, type_=None, priv=None, daterange=None, datespan=None, dateval=None, datestr=None, temple=None, place=None, status=None, sealed_to=None, noteref=None, citationref=None):
        super(lds_ordSub, self).__init__(type_, priv, daterange, datespan, dateval, datestr, temple, place, status, sealed_to, noteref, citationref, )
supermod.lds_ord.subclass = lds_ordSub
# end class lds_ordSub


class templeSub(supermod.temple):
    def __init__(self, val=None):
        super(templeSub, self).__init__(val, )
supermod.temple.subclass = templeSub
# end class templeSub


class statusSub(supermod.status):
    def __init__(self, val=None):
        super(statusSub, self).__init__(val, )
supermod.status.subclass = statusSub
# end class statusSub


class sealed_toSub(supermod.sealed_to):
    def __init__(self, hlink=None):
        super(sealed_toSub, self).__init__(hlink, )
supermod.sealed_to.subclass = sealed_toSub
# end class sealed_toSub



def get_root_tag(node):
    tag = supermod.Tag_pattern_.match(node.tag).groups()[-1]
    rootClass = None
    if hasattr(supermod, tag):
        rootClass = getattr(supermod, tag)
    return tag, rootClass


def parse(inFilename):
    doc = parsexml_(inFilename)
    rootNode = doc.getroot()
    rootTag, rootClass = get_root_tag(rootNode)
    if rootClass is None:
        rootTag = 'database'
        rootClass = supermod.database
    rootObj = rootClass.factory()
    rootObj.build(rootNode)
    # Enable Python to collect the space used by the DOM.
    doc = None
    sys.stdout.write('<?xml version="1.0" ?>\n')
    rootObj.export(sys.stdout, 0, name_=rootTag,
        namespacedef_='')
    doc = None
    return rootObj


def parseString(inString):
    from StringIO import StringIO
    doc = parsexml_(StringIO(inString))
    rootNode = doc.getroot()
    rootTag, rootClass = get_root_tag(rootNode)
    if rootClass is None:
        rootTag = 'database'
        rootClass = supermod.database
    rootObj = rootClass.factory()
    rootObj.build(rootNode)
    # Enable Python to collect the space used by the DOM.
    doc = None
    sys.stdout.write('<?xml version="1.0" ?>\n')
    rootObj.export(sys.stdout, 0, name_=rootTag,
        namespacedef_='')
    return rootObj


def parseLiteral(inFilename):
    doc = parsexml_(inFilename)
    rootNode = doc.getroot()
    rootTag, rootClass = get_root_tag(rootNode)
    if rootClass is None:
        rootTag = 'database'
        rootClass = supermod.database
    rootObj = rootClass.factory()
    rootObj.build(rootNode)
    # Enable Python to collect the space used by the DOM.
    doc = None
    sys.stdout.write('#from ??? import *\n\n')
    sys.stdout.write('import ??? as model_\n\n')
    sys.stdout.write('rootObj = model_.database(\n')
    rootObj.exportLiteral(sys.stdout, 0, name_="database")
    sys.stdout.write(')\n')
    return rootObj


USAGE_TEXT = """
Usage: python ???.py <infilename>
"""

def usage():
    print USAGE_TEXT
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if len(args) != 1:
        usage()
    infilename = args[0]
    root = parse(infilename)


if __name__ == '__main__':
    #import pdb; pdb.set_trace()
    main()


