from lxml import etree

from itertools import *
from more_itertools import *


class TeiWriter:

    def __init__(self):
        self.root = etree.Element('teiCorpus')
        self.root.attrib['xmlns'] = "http://www.tei-c.org/ns/1.0"

        self.current_title = None
        self.current_author = None
        self.current_poem = None
        self.current_stanza = None
        self.page_counter = 0

    def close_poem(self):
        if self.current_poem is None:
            # Operation ist idempotent
            return

        # enthält das aktuelle Gedicht keine Zeilen, wird es nicht ausgegeben
        if len(self.current_poem.xpath('.//l')) == 0:
            return

        tei_el = etree.SubElement(self.root, 'TEI')
        title_stmt = etree.SubElement(etree.SubElement(etree.SubElement(
            tei_el, 'teiHeader'), 'fileDesc'), 'titleStmt')
        etree.SubElement(title_stmt, 'title').text = self.current_title
        etree.SubElement(title_stmt, 'author').text = self.current_author

        body = etree.SubElement(etree.SubElement(tei_el, 'text'), 'body')
        body.append(self.current_poem)
        self.current_poem = None

    def open_poem(self):
        if self.current_poem is not None:
            # Operation ist idempotent
            return

        self.current_title = None
        self.current_author = None
        self.current_stanza = None
        self.current_poem = etree.Element('div')
        self.current_poem.attrib['type'] = 'poem'

    def close_stanza(self):
        if self.current_stanza is None:
            return

        self.current_poem.append(self.current_stanza)
        self.current_stanza = None

    def open_stanza(self):
        self.current_stanza = etree.Element('lg')

    def add_line(self, text):
        etree.SubElement(self.current_stanza, 'l').text = text

    def add_title(self, text):
        head = etree.SubElement(self.current_poem, 'head')
        head.text = text
        head.attrib['type'] = 'head'

    def add_byline(self, text):
        byline = etree.Element('byline')
        byline.text = text
        self.current_poem.append(byline)

    def add_pb(self, pagefile):
        if self.current_poem is None:
            return

        if self.current_stanza is not None:
            el = etree.SubElement(self.current_stanza, 'pb')
        else:
            el = etree.SubElement(self.current_poem, 'pb')
    
        el.attrib['facs'] = pagefile
        el.attrib['n'] = str(self.page_counter)
        self.page_counter += 1

    def add_fw(self, fwtype, text):
        if self.current_poem is None:
            return

        if self.current_stanza is not None:
            parent = self.current_stanza
        else:
            parent = self.current_poem

        last_el = parent[-1:]
        if len(last_el)>0 and last_el[0].tag == 'fw' and last_el[0].attrib['type'] == fwtype:
            # Füge nächste Zeile ein
            br = etree.SubElement(last_el[0], 'br')
            br.tail = text
        else:
            el = etree.SubElement(parent, 'fw')
            el.attrib['type'] = fwtype
            el.text = text


    def process(self, elements):
        p = _process_ignored(map(_map_el, elements))

        # starte mit erstem Gedicht
        self.open_poem()

        for el in p:
            self.process_element(el)

        # schließe noch offene Elemente
        self.close_stanza()
        self.close_poem()

    def process_element(self, el):
        tagname = el['tagname']
        classes = el['classes']

        if 'gedicht-start' in classes:
            self.close_stanza()
            self.close_poem()
            self.open_poem()

        if 'titel' in classes:
            self.current_title = el['text']
            self.close_stanza()
            self.add_title(el['text'])

        if 'autor' in classes:
            self.current_author = el['text']
            self.close_stanza()
            self.add_byline(el['text'])

        if 'strophe-start' in classes:
            self.close_stanza()
            self.open_stanza()

        if 'vers' in classes:
            self.add_line(el['text'])

        if tagname == 'PageBreak':
            self.add_pb(el['pagefile'])

        if 'kopfzeile' in classes:
            self.add_fw('header', el['text'])

        if 'fusszeile' in classes:
            self.add_fw('footer', el['text'])


# Ordnet jedem Element im XML-Dokument ein Dict zu, mit Tagname, Klassen, optional Text, optional Seiteninformation
def _map_el(el):
    ret = {}
    ret['tagname'] = el.tag
    attributes = dict(map(lambda a: (a.attrib['key'], a.attrib['value']), el.xpath('.//Annotation')))
    if 'classes' in attributes:
        ret['classes'] = attributes['classes'].split(' ')
    else:
        ret['classes'] = []

    if el.xpath('./TextEquiv'):
        ret['text'] = el.xpath('./TextEquiv')[0].text

    if el.tag == 'PageBreak':
        ret['pagefile'] = el.attrib['filename']

    return ret


# Verändert den Eingabeiterator so, dass 'ignore'-Abstände zwei Elemente
# mit gleichen Klassen zusammenführt.
def _process_ignored(it):
    it = peekable(it)
    try:
        while True:
            el = next(it)

            while True:
                try:
                    nextEl = it.peek() # 1-Lookahead
                    if nextEl is None: break

                    if (el['tagname'] == nextEl['tagname'] and el['classes'] == nextEl['classes']) or ('ignore' in nextEl['classes']):
                        next(it) # Inkrementiere Pointer

                        # Akkumuliere Text in el
                        if 'text' in el and 'text' in nextEl: el['text'] = el['text'] + ' ' + nextEl['text'] 
                    else:
                        break
                except StopIteration:
                    break

            yield el
    except StopIteration:
        pass
