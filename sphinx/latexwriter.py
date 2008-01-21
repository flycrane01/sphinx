# -*- coding: utf-8 -*-
"""
    sphinx.latexwriter
    ~~~~~~~~~~~~~~~~~~

    Custom docutils writer for LaTeX.

    Much of this code is adapted from Dave Kuhlman's "docpy" writer from his
    docutils sandbox.

    :copyright: 2007-2008 by Georg Brandl, Dave Kuhlman.
    :license: BSD.
"""

import re
import time
import string

from docutils import frontend, nodes, languages, writers, utils

from sphinx import addnodes
from sphinx import highlighting

# Move to a template?
HEADER = r'''%% Generated by Sphinx.
\documentclass[%(papersize)s,%(pointsize)s]{%(docclass)s}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[colorlinks,breaklinks]{hyperref}
\title{%(title)s}
\date{%(date)s}
\release{%(release)s}
\author{%(author)s}
%(preamble)s
\makeindex
\makemodindex
'''

FOOTER = r'''
\printmodindex
\printindex
\end{document}
'''


class LaTeXWriter(writers.Writer):

    supported = ('sphinxlatex',)

    settings_spec = ('No options here.', '', ())
    settings_defaults = {}

    output = None

    def __init__(self, builder):
        writers.Writer.__init__(self)
        self.builder = builder

    def translate(self):
        try:
            visitor = LaTeXTranslator(self.document, self.builder)
            self.document.walkabout(visitor)
            self.output = visitor.astext()
        except:
            import pdb, sys, traceback
            traceback.print_exc()
            tb = sys.exc_info()[2]
            pdb.post_mortem(tb)


# Helper classes

class TableSpec:
    def __init__(self):
        self.columnCount = 0
        self.firstRow = 1

class Desc:
    def __init__(self, node):
        self.env = LaTeXTranslator.desc_map[node['desctype']]
        self.ni = node['noindex']
        self.type = self.cls = self.name = self.params = ''
        self.count = 0


class LaTeXTranslator(nodes.NodeVisitor):
    sectionnames = ["chapter", "chapter", "section", "subsection",
                    "subsubsection", "paragraph", "subparagraph"]

    def __init__(self, document, builder):
        nodes.NodeVisitor.__init__(self, document)
        self.builder = builder
        self.body = []
        docclass = document.settings.docclass
        paper = builder.config.latex_paper_size + 'paper'
        if paper == 'paper': # e.g. command line "-D latex_paper_size="
            paper = 'letterpaper'
        date = time.strftime(builder.config.today_fmt)
        self.options = {'docclass': docclass,
                        'papersize': paper,
                        'pointsize': builder.config.latex_font_size,
                        'preamble': builder.config.latex_preamble,
                        'author': document.settings.author,
                        'filename': document.settings.filename,
                        'title': None, # is determined later
                        'release': builder.config.release,
                        'date': date,
                        }
        self.context = []
        self.descstack = []
        self.highlightlang = 'python'
        self.written_ids = set()
        if docclass == 'manual':
            self.top_sectionlevel = 0
        else:
            self.top_sectionlevel = 1
        # flags
        self.verbatim = None
        self.in_title = 0
        self.in_production_list = 0
        self.first_document = 1
        self.this_is_the_title = 1
        self.literal_whitespace = 0

    def astext(self):
        return (HEADER % self.options) + \
               highlighting.get_stylesheet('latex') + '\n\n' + \
               u''.join(self.body) + \
               (FOOTER % self.options)

    def visit_document(self, node):
        if self.first_document == 1:
            self.body.append('\\begin{document}\n\\maketitle\n\\tableofcontents\n')
            self.first_document = 0
        elif self.first_document == 0:
            self.body.append('\n\\appendix\n')
            self.first_document = -1
        self.sectionlevel = self.top_sectionlevel
    def depart_document(self, node):
        pass

    def visit_highlightlang(self, node):
        self.highlightlang = node['lang']
        raise nodes.SkipNode

    def visit_comment(self, node):
        raise nodes.SkipNode

    def visit_section(self, node):
        if not self.this_is_the_title:
            self.sectionlevel += 1
        self.body.append('\n\n')
        if node.get('ids'):
            for id in node['ids']:
                if id not in self.written_ids:
                    self.body.append(r'\hypertarget{%s}{}' % id)
                    self.written_ids.add(id)
    def depart_section(self, node):
        self.sectionlevel -= 1

    def visit_problematic(self, node):
        self.body.append(r'{\color{red}\bfseries{}')
    def depart_problematic(self, node):
        self.body.append('}')

    def visit_topic(self, node):
        self.body.append('\\begin{center}\\setlength{\\fboxsep}{5pt}'
                         '\\fbox{\\begin{minipage}{0.95\\textwidth}\n')
    def depart_topic(self, node):
        self.body.append('\end{minipage}}\\end{center}\n')
    visit_sidebar = visit_topic
    depart_sidebar = depart_topic

    def visit_glossary(self, node):
        pass
    def depart_glossary(self, node):
        pass

    def visit_productionlist(self, node):
        self.body.append('\n\n\\begin{productionlist}\n')
        self.in_production_list = 1
    def depart_productionlist(self, node):
        self.body.append('\\end{productionlist}\n\n')
        self.in_production_list = 0

    def visit_production(self, node):
        if node['tokenname']:
            self.body.append('\\production{%s}{' % self.encode(node['tokenname']))
        else:
            self.body.append('\\productioncont{')
    def depart_production(self, node):
        self.body.append('}\n')

    def visit_transition(self, node):
        self.body.append('\n\n\\bigskip\\hrule{}\\bigskip\n\n')
    def depart_transition(self, node):
        pass

    def visit_title(self, node):
        if isinstance(node.parent, addnodes.seealso):
            # the environment already handles this
            raise nodes.SkipNode
        elif self.this_is_the_title:
            if len(node.children) != 1 and not isinstance(node.children[0], Text):
                self.builder.warn('document title is not a single Text node')
            self.options['title'] = node.astext()
            self.this_is_the_title = 0
            raise nodes.SkipNode
        elif isinstance(node.parent, nodes.section):
            self.body.append(r'\%s{' % self.sectionnames[self.sectionlevel])
            self.context.append('}\n')
        elif isinstance(node.parent, (nodes.topic, nodes.sidebar)):
            self.body.append(r'\textbf{')
            self.context.append('}\n\n\medskip\n\n')
        else:
            self.builder.warn('encountered title node not in section, topic or sidebar')
            self.body.append('\\textbf{')
            self.context.append('}')
        self.in_title = 1
    def depart_title(self, node):
        self.in_title = 0
        self.body.append(self.context.pop())

    desc_map = {
        'function' : 'funcdesc',
        'class': 'classdesc',
        'method': 'methoddesc',
        'exception': 'excdesc',
        'data': 'datadesc',
        'attribute': 'memberdesc',
        'opcode': 'opcodedesc',

        'cfunction': 'cfuncdesc',
        'cmember': 'cmemberdesc',
        'cmacro': 'csimplemacrodesc',
        'ctype': 'ctypedesc',
        'cvar': 'cvardesc',

        'describe': 'describe',
        'cmdoption': 'describe',
        'envvar': 'describe',
    }

    def visit_desc(self, node):
        self.descstack.append(Desc(node))
    def depart_desc(self, node):
        d = self.descstack.pop()
        self.body.append("\\end{%s%s}\n" % (d.env, d.ni and 'ni' or ''))

    def visit_desc_signature(self, node):
        pass
    def depart_desc_signature(self, node):
        d = self.descstack[-1]
        d.cls = d.cls.rstrip('.')
        if node.parent['desctype'] != 'describe' and node['ids']:
            hyper = '\\hypertarget{%s}{}' % node['ids'][0]
        else:
            hyper = ''
        if d.count == 0:
            t1 = "\n\n%s\\begin{%s%s}" % (hyper, d.env, (d.ni and 'ni' or ''))
        else:
            t1 = "\n%s\\%sline%s" % (hyper, d.env[:-4], (d.ni and 'ni' or ''))
        d.count += 1
        if d.env in ('funcdesc', 'classdesc', 'excclassdesc'):
            t2 = "{%s}{%s}" % (d.name, d.params)
        elif d.env in ('datadesc', 'classdesc*', 'excdesc', 'csimplemacrodesc'):
            t2 = "{%s}" % (d.name)
        elif d.env == 'methoddesc':
            t2 = "[%s]{%s}{%s}" % (d.cls, d.name, d.params)
        elif d.env == 'memberdesc':
            t2 = "[%s]{%s}" % (d.cls, d.name)
        elif d.env == 'cfuncdesc':
            t2 = "{%s}{%s}{%s}" % (d.type, d.name, d.params)
        elif d.env == 'cmemberdesc':
            try:
                type, container = d.type.rsplit(' ', 1)
                container = container.rstrip('.')
            except:
                container = ''
                type = d.type
            t2 = "{%s}{%s}{%s}" % (container, type, d.name)
        elif d.env == 'cvardesc':
            t2 = "{%s}{%s}" % (d.type, d.name)
        elif d.env == 'ctypedesc':
            t2 = "{%s}" % (d.name)
        elif d.env == 'opcodedesc':
            t2 = "{%s}{%s}" % (d.name, d.params)
        elif d.env == 'describe':
            t2 = "{%s}" % d.name
        self.body.append(t1 + t2)

    def visit_desc_type(self, node):
        self.descstack[-1].type = self.encode(node.astext().strip())
        raise nodes.SkipNode

    def visit_desc_name(self, node):
        self.descstack[-1].name = self.encode(node.astext().strip())
        raise nodes.SkipNode

    def visit_desc_classname(self, node):
        self.descstack[-1].cls = self.encode(node.astext().strip())
        raise nodes.SkipNode

    def visit_desc_parameterlist(self, node):
        self.descstack[-1].params = self.encode(node.astext().strip())
        raise nodes.SkipNode

    def visit_refcount(self, node):
        self.body.append("\\emph{")
    def depart_refcount(self, node):
        self.body.append("}\\\\")

    def visit_desc_content(self, node):
        pass
    def depart_desc_content(self, node):
        pass

    def visit_seealso(self, node):
        self.body.append("\n\n\\begin{seealso}\n")
    def depart_seealso(self, node):
        self.body.append("\n\\end{seealso}\n")

    def visit_rubric(self, node):
        if len(node.children) == 1 and node.children[0].astext() == 'Footnotes':
            raise nodes.SkipNode
        self.builder.warn('encountered rubric node not used for footnotes, '
                          'content will be lost')

    def visit_footnote(self, node):
        # XXX not optimal, footnotes are at section end
        num = node.children[0].astext().strip()
        self.body.append('\\footnotetext[%s]{' % num)
    def depart_footnote(self, node):
        self.body.append('}')

    def visit_label(self, node):
        raise nodes.SkipNode

    def visit_table(self, node):
        self.tableSpec = TableSpec()
    def depart_table(self, node):
        self.tableSpec = None

    def visit_colspec(self, node):
        pass
    def depart_colspec(self, node):
        pass

    def visit_tgroup(self, node):
        columnCount = int(node.get('cols', 0))
        self.tableSpec.columnCount = columnCount
        if columnCount == 2:
            self.body.append('\\begin{tableii}{l|l}{textrm}')
        elif columnCount == 3:
            self.body.append('\\begin{tableiii}{l|l|l}{textrm}')
        elif columnCount == 4:
            self.body.append('\\begin{tableiv}{l|l|l|l}{textrm}')
        elif columnCount == 5:
            self.body.append('\\begin{tablev}{l|l|l|l|l}{textrm}')
        else:
            self.builder.warn('table with too many columns, ignoring')
            raise nodes.SkipNode
    def depart_tgroup(self, node):
        if self.tableSpec.columnCount == 2:
            self.body.append('\n\\end{tableii}\n\n')
        elif self.tableSpec.columnCount == 3:
            self.body.append('\n\\end{tableiii}\n\n')
        elif self.tableSpec.columnCount == 4:
            self.body.append('\n\\end{tableiv}\n\n')
        elif self.tableSpec.columnCount == 5:
            self.body.append('\n\\end{tablev}\n\n')

    def visit_thead(self, node):
        pass
    def depart_thead(self, node):
        pass

    def visit_tbody(self, node):
        pass
    def depart_tbody(self, node):
        pass

    def visit_row(self, node):
        if not self.tableSpec.firstRow:
            if self.tableSpec.columnCount == 2:
                self.body.append('\n\\lineii')
            elif self.tableSpec.columnCount == 3:
                self.body.append('\n\\lineiii')
            elif self.tableSpec.columnCount == 4:
                self.body.append('\n\\lineiv')
            elif self.tableSpec.columnCount == 5:
                self.body.append('\n\\linev')
    def depart_row(self, node):
        if self.tableSpec.firstRow:
            self.tableSpec.firstRow = 0

    def visit_entry(self, node):
        if self.tableSpec.firstRow:
            self.body.append('{%s}' % self.encode(node.astext().strip(' ')))
            raise nodes.SkipNode
        else:
            self.body.append('{')
    def depart_entry(self, node):
        if self.tableSpec.firstRow:
            pass
        else:
            self.body.append('}')

    def visit_acks(self, node):
        # this is a list in the source, but should be rendered as a
        # comma-separated list here
        self.body.append('\n\n')
        self.body.append(', '.join(n.astext() for n in node.children[0].children) + '.')
        self.body.append('\n\n')
        raise nodes.SkipNode

    def visit_bullet_list(self, node):
        self.body.append('\\begin{itemize}\n' )
    def depart_bullet_list(self, node):
        self.body.append('\\end{itemize}\n' )

    def visit_enumerated_list(self, node):
        self.body.append('\\begin{enumerate}\n' )
    def depart_enumerated_list(self, node):
        self.body.append('\\end{enumerate}\n' )

    def visit_list_item(self, node):
        # Append "{}" in case the next character is "[", which would break
        # LaTeX's list environment (no numbering and the "[" is not printed).
        self.body.append(r'\item {} ')
    def depart_list_item(self, node):
        self.body.append('\n')

    def visit_definition_list(self, node):
        self.body.append('\\begin{description}\n')
    def depart_definition_list(self, node):
        self.body.append('\\end{description}\n')

    def visit_definition_list_item(self, node):
        pass
    def depart_definition_list_item(self, node):
        pass

    def visit_term(self, node):
        ctx = ']'
        if node.has_key('ids') and node['ids']:
            ctx += '\\hypertarget{%s}{}' % node['ids'][0]
        self.body.append('\\item[')
        self.context.append(ctx)
    def depart_term(self, node):
        self.body.append(self.context.pop())

    def visit_classifier(self, node):
        self.body.append('{[}')
    def depart_classifier(self, node):
        self.body.append('{]}')

    def visit_definition(self, node):
        pass
    def depart_definition(self, node):
        self.body.append('\n')

    def visit_field_list(self, node):
        self.body.append('\\begin{quote}\\begin{description}\n')
    def depart_field_list(self, node):
        self.body.append('\\end{description}\\end{quote}\n')

    def visit_field(self, node):
        pass
    def depart_field(self, node):
        pass

    visit_field_name = visit_term
    depart_field_name = depart_term

    visit_field_body = visit_definition
    depart_field_body = depart_definition

    def visit_paragraph(self, node):
        self.body.append('\n')
    def depart_paragraph(self, node):
        self.body.append('\n')

    def visit_centered(self, node):
        self.body.append('\n\\begin{centering}')
    def depart_centered(self, node):
        self.body.append('\n\\end{centering}')

    def visit_module(self, node):
        modname = node['modname']
        self.body.append('\\declaremodule[%s]{}{%s}' % (modname.replace('_', ''),
                                                        self.encode(modname)))
        self.body.append('\\modulesynopsis{%s}' % self.encode(node['synopsis']))
        if node.has_key('platform'):
            self.body.append('\\platform{%s}' % self.encode(node['platform']))
    def depart_module(self, node):
        pass

    def visit_note(self, node):
        self.body.append('\n\\begin{notice}[note]')
    def depart_note(self, node):
        self.body.append('\\end{notice}\n')

    def visit_warning(self, node):
        self.body.append('\n\\begin{notice}[warning]')
    def depart_warning(self, node):
        self.body.append('\\end{notice}\n')

    def visit_versionmodified(self, node):
        self.body.append('\\%s' % node['type'])
        if node['type'] == 'deprecated':
            self.body.append('{%s}{' % node['version'])
            self.context.append('}')
        else:
            if len(node):
                self.body.append('[')
                self.context.append(']{%s}' % node['version'])
            else:
                self.body.append('{%s}' % node['version'])
                self.context.append('')
    def depart_versionmodified(self, node):
        self.body.append(self.context.pop())

    def visit_target(self, node):
        def add_target(id):
            # indexing uses standard LaTeX index markup, so the targets
            # will be generated differently
            if not id.startswith('index-'):
                self.body.append(r'\hypertarget{%s}{' % id)
                return '}'
            return ''

        if not (node.has_key('refuri') or node.has_key('refid')
                or node.has_key('refname')):
            ctx = ''
            for id in node['ids']:
                if id not in self.written_ids:
                    self.written_ids.add(id)
                    ctx += add_target(id)
            self.context.append(ctx)
        elif node.has_key('refid') and node['refid'] not in self.written_ids:
            self.context.append(add_target(node['refid']))
            self.written_ids.add(node['refid'])
        else:
            self.context.append('')
    def depart_target(self, node):
        self.body.append(self.context.pop())

    indextype_map = {
        'module': 'refmodindex',
        'keyword': 'kwindex',
        'operator': 'opindex',
        'object': 'obindex',
        'exception': 'exindex',
        'statement': 'stindex',
        'builtin': 'bifuncindex',
    }

    def visit_index(self, node, scre=re.compile(r';\s*')):
        entries = node['entries']
        for type, string, tid, _ in entries:
            if type == 'single':
                self.body.append(r'\index{%s}' % scre.sub('!', self.encode(string)))
            elif type == 'pair':
                parts = tuple(self.encode(x.strip()) for x in string.split(';', 1))
                self.body.append(r'\indexii{%s}{%s}' % parts)
            elif type == 'triple':
                parts = tuple(self.encode(x.strip()) for x in string.split(';', 2))
                self.body.append(r'\indexiii{%s}{%s}{%s}' % parts)
            elif type in self.indextype_map:
                self.body.append(r'\%s{%s}' % (self.indextype_map[type],
                                               self.encode(string)))
            else:
                self.builder.warn('unknown index entry type %s found' % type)
        raise nodes.SkipNode

    def visit_reference(self, node):
        uri = node.get('refuri', '')
        if self.in_title or not uri:
            self.context.append('')
        elif uri.startswith('mailto:') or uri.startswith('http:') or \
             uri.startswith('ftp:'):
            self.body.append('\\href{%s}{' % self.encode(uri))
            self.context.append('}')
        elif uri.startswith('#'):
            self.body.append('\\hyperlink{%s}{' % uri[1:])
            self.context.append('}')
        elif uri.startswith('@token'):
            if self.in_production_list:
                self.body.append('\\token{')
            else:
                self.body.append('\\grammartoken{')
            self.context.append('}')
        else:
            self.builder.warn('malformed reference target found: %s' % uri)
            self.context.append('')
    def depart_reference(self, node):
        self.body.append(self.context.pop())

    def visit_pending_xref(self, node):
        pass
    def depart_pending_xref(self, node):
        pass

    def visit_emphasis(self, node):
        self.body.append(r'\emph{')
    def depart_emphasis(self, node):
        self.body.append('}')

    def visit_literal_emphasis(self, node):
        self.body.append(r'\emph{\texttt{')
    def depart_literal_emphasis(self, node):
        self.body.append('}}')

    def visit_strong(self, node):
        self.body.append(r'\textbf{')
    def depart_strong(self, node):
        self.body.append('}')

    def visit_title_reference(self, node):
        self.body.append(r'\emph{')
    def depart_title_reference(self, node):
        self.body.append('}')

    def visit_literal(self, node):
        content = self.encode(node.astext().strip())
        if self.in_title:
            self.body.append(r'\texttt{%s}' % content)
        elif re.search('[ \t\n]', content):
            self.body.append(r'\samp{%s}' % content)
        else:
            self.body.append(r'\code{%s}' % content)
        raise nodes.SkipNode

    def visit_footnote_reference(self, node):
        self.body.append('\\footnotemark[%s]' % node.astext())
        raise nodes.SkipNode

    def visit_literal_block(self, node):
        self.verbatim = ''
    def depart_literal_block(self, node):
        hlcode = highlighting.highlight_block(self.verbatim.rstrip('\n'),
                                              self.highlightlang, 'latex')
        # workaround for Unicode issue
        hlcode = hlcode.replace(u'€', u'@texteuro[]')
        # workaround for Pygments bug
        hlcode = hlcode.replace('\n\\end{Verbatim}', '\\end{Verbatim}')
        self.body.append('\n' + hlcode)
        self.verbatim = None
    visit_doctest_block = visit_literal_block
    depart_doctest_block = depart_literal_block

    def visit_line_block(self, node):
        """line-block:
        * whitespace (including linebreaks) is significant
        * inline markup is supported.
        * serif typeface
        """
        self.body.append('\\begin{flushleft}\n')
        self.literal_whitespace = 1
    def depart_line_block(self, node):
        self.literal_whitespace = 0
        self.body.append('\n\\end{flushleft}\n')

    def visit_line(self, node):
        pass
    def depart_line(self, node):
        pass

    def visit_block_quote(self, node):
        # If the block quote contains a single object and that object
        # is a list, then generate a list not a block quote.
        # This lets us indent lists.
        done = 0
        if len(node.children) == 1:
            child = node.children[0]
            if isinstance(child, nodes.bullet_list) or \
                    isinstance(child, nodes.enumerated_list):
                done = 1
        if not done:
            self.body.append('\\begin{quote}\n')
    def depart_block_quote(self, node):
        done = 0
        if len(node.children) == 1:
            child = node.children[0]
            if isinstance(child, nodes.bullet_list) or \
                    isinstance(child, nodes.enumerated_list):
                done = 1
        if not done:
            self.body.append('\\end{quote}\n')

    replacements = [
        (u"\\", u"\x00"),
        (u"$", ur"\$"),
        (r"%", ur"\%"),
        (u"&", ur"\&"),
        (u"#", ur"\#"),
        (u"_", ur"\_"),
        (u"{", ur"\{"),
        (u"}", ur"\}"),
        (u"[", ur"{[}"),
        (u"]", ur"{]}"),
        (u"¶", ur"\P{}"),
        (u"§", ur"\S{}"),
        (u"∞", ur"$\infinity$"),
        (u"±", ur"$\pm$"),
        (u"‣", ur"$\rightarrow$"),
        (u"Ω", ur"$\Omega$"),
        (u"Ω", ur"$\Omega$"),
        (u"~", ur"\textasciitilde{}"),
        (u"€", ur"\texteuro{}"),
        (u"<", ur"\textless{}"),
        (u">", ur"\textgreater{}"),
        (u"^", ur"\textasciicircum{}"),
        (u"\x00", ur"\textbackslash{}"),
    ]

    def encode(self, text):
        for x, y in self.replacements:
            text = text.replace(x, y)
        if self.literal_whitespace:
            # Insert a blank before the newline, to avoid
            # ! LaTeX Error: There's no line here to end.
            text = text.replace("\n", '~\\\\\n').replace(" ", "~")
        return text

    def visit_Text(self, node):
        if self.verbatim is not None:
            self.verbatim += node.astext()
        else:
            self.body.append(self.encode(node.astext()))
    def depart_Text(self, node):
        pass

    def unknown_visit(self, node):
        raise NotImplementedError("Unknown node: " + node.__class__.__name__)
