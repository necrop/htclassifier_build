
import re

from regexcompiler import ReplacementListCompiler


primarystripper = ReplacementListCompiler((
    (r'<.[^<>]*/>', ' '), # remove empty tags
    (r'<([a-zA-Z]+) [^<>]*>', r'<\1>'), # remove tag attributes
    (r'(<def>|</def>|<header>|</header>)', ''),
    (r'</subDef>.*$', ''),
    (r'(<subDef>|</subDef>)', ''),
    (r'\.</(la|gr)> ([A-Z][a-z])', r'</\1>. \2'),
    (r'\.</(la|gr)>', r'</\1>'),
    (r'(esp|spec|orig|freq|usu|cf|phr|perh)\.', r'\1'),
    (r'(Esp|Spec|Orig|Freq|Usu|Cf|Phr|Perh|App)\.', r'\1'),
    (r' (pl|sing)\. ([a-z])', r' \1 \2'),
    (r', esp [a-z]+ly, ', r' '),
    (r'([ >(][A-Z])\. ', r'\1 ')
))
headstripper = ReplacementListCompiler((
    (r'[Ww]ith (pl|sing|plural|singular) [^.]+\. ([A-Z][a-z]|A )', r'\2'),
    (r'[Ww]ith <gr>[^<>]+</gr>(| (and|or) <gr>[^<>]+</gr>) concord([.:]|$)', ''),
    (r'Also (with|as) [^.]+\. ([A-Z][a-z]|A )', '\2'),
    (r'Forming (nouns|verbs|adjectives|adverbs)(, as |, | )', ''),
    (r'^[^.:]+.: ', ''),
    (r'^[Aa]s a (mass|count) noun[.: ]+', ''),
    (r'^[Ww]ith(|out) (const|complement|direct obj|indirect obj|capital initial)([.:]|$)', ''),
    (r'^In [a-z]+ use[.:]', ''),
    (r'^([Mm]isprint|[Ee]rror) for ', ''),
    (r'^\([^()]+\) ', ''),
    (r'^<la>[^<>]+</la> \([^()]+\)\. ', ''),
    (r'^<gr>[^<>]+</gr> \([^()]+\)\. ', ''),
))
tailstripper = ReplacementListCompiler((
    (r'(([ -][a-z]{3,}| [A-Z][a-z]{4,})\.\)?) \(?([A-Z][a-z]|<la>).*$', r'\1'),
    (r'(\)\.) [A-Z][a-z].*$', r'\1'),
    (r'( [a-z]+ [a-z]{3,}\.) <la>(Obs|rare)*$', r'\1'),
    (r'(\.) (Also|Now)[:, ].*$', r'\1'),
    (r' (Cf|See) .*$', r''),
    (r'; \(?(formerly|chiefly|usu|freq|spec|also|more usually).*$', ''),
    (r'([a-z]{3}\.) <cf>.*$', r'\1'),
    (r': (see|e\.g\.) .*$', ''),
    (r', (used |now |)(esp|especially) [^(),].*$', '')
))
glosscleaner = ReplacementListCompiler((
    (r' *(also |now |)(chiefly|formerly|orig|usu|freq|spec|with|in|hence|esp|now only)(| in) <(la|lm|lemUnit|gr)>', r' <\4>'),
    (r'(also|usually |)(more fully|in full|in form) <(lm|lemUnit|vf)>', r' <\3>'),
    #(r' *(cf\.|see|see also|=) *<(xr|cf)', r' <\2'),
    (r'</la>,? *(,|and|or) *<la>', '</la><la>'),
    (r'</(gr|ps)> *(,|and|or) *<(gr|ps)>', r'</\1><\3>'),
    (r' *<(la|lm|w|dat|datEnd|gr|xs|xd|vf)>.*?</\1> *', ' '),
    (r' *<lemUnit>.*?</lemUnit> *', ' '),
    (r' *<labels>.*?</labels> *', ' '),
    (r' *with <cf>[^<>]+</cf>', ' '),
    (r',? etc\.?,?', ' '),
    (r'&#\d+;', ' '),
    (r'see quots\.?', ' '),
    (r'see quot\.?', ' '),
    (r'\([ .,;]*\)', ' '),
    (r'\((see|in|also|as|for|cf|or|with|chiefly|formerly|freq|usu|orig|esp|spec|originally|usually|sense|=) [^()]+\)', ' '),
    (r'\((also|now|orig|esp|formerly|chiefly|freq|more commonly|less commonly)\)', ' '),
    (r'\((cockeram|johnson|jamieson|blount|knight)\)', ' '),
    (r'\(<xr>[^()]+</xr>\)', ' '),
    (r' (usu|freq|esp|orig|spec)\.? ', ' '),
    (r'<[^<>]*>', ' '),
    (r'  +', ' '),
    (r', *,', ','),
    (r'(^[ .,;:?]+|[ .,;:?]+$)', ''),
    (r'; .*$', ''),
    (r'^(only|or|and|also|phr|spec)$', ''),
    (r' +([,:;)])', r'\1'),
), caseInsensitive=True)


def definition_to_gloss(def_serialized, wordclass):
    """
    Attempts to return just the gloss part of the definition, without
    leading or trailing labels, cross-reference, etc.
    """
    cleaned = primarystripper.edit(def_serialized)
    for i in (1, 2):
        cleaned = headstripper.edit(cleaned.strip())
        cleaned = tailstripper.edit(cleaned.strip())
        cleaned = glosscleaner.edit(cleaned.strip())
    if cleaned.startswith('Cf. '):
        cleaned = ''
    if wordclass == 'NN' and cleaned.startswith('In '):
        cleaned = ''
    return cleaned


generics = '(number|series|form|sort|type|variety|variant|version|kind|set|class|group|collection|style)'
statelike = '(act|process|action|property|state|condition|fact|quality|instance|practice)'
adverbs = '(sometimes|often|always|almost|perhaps|rather|quite|somewhat|such|enough|certain)'
adverbly = '(usual|occasional|frequent|chief|common|former|general|original|possib|real|slight|typical)ly'
phrasals = '(a|an|the|by|with|from|at|in|into|on|onto|upon|out|through|away|to|oneself|about|[a-z]+ly)'
causal = '(give rise to|bring about|engender|produce|induce|cause|compel)'
transform = '(become|(turn|grow|pass|change|develop|evolve) into)'

glossnormal = ReplacementListCompiler ((
    (r'\(.*?\)', ''),  # remove bracketed content
    (r' ' + adverbs + ' ', ' '),
    (r' ' + adverbly + ' ', ' '),
    (r' (either|any) of (various|several|two|three) ' + generics + 's of ', ' '),
    (r' various ' + generics + 's of ', ' '),
    (r' any of various ', ' '),
    (r' various ', ' '),
    (r' (some|any) ' + generics + ' of ', ' '),
    (r' (one|each) of a pair of ', ' '),
    (r' (any|each|either) of ', ' '),
    (r' (a|an|the) ' + generics + ' or ' + generics + ' of ', ' a '),
    (r' (a|an|the) ([a-z]+ |)' + generics + ' of ', ' a '),
    (r' ' + generics + ' of ', ' '),
    (r'  +', ' '),
    (r' (a |an |the |)([a-z]+ |)name (for|of) ', ' '),
    (r' (term|name)s? (applied to|given to|for) ', ' '),
    (r' (corruption of|error for) ', ' '),
    (r'someone', r'a person'),
    (r'(anything|something)', 'a thing'),
    (r' person or (a |)thing', ' person'),
    (r' person who or (a |)thing which', ' person who'),
    (r' ' + statelike + ' of ', ' state of '),
    (r' ' + statelike + ' or (a |an |)' + statelike + ' of ', ' state of '),
    (r' ' + causal + ' ', ' cause '),
    (r' ' + transform + ' ', ' become '),
    #(r' ([a-z-]+), [a-z-]+, or [a-z-]{4,} ', r' \1 '),
    #(r' ([a-z-]+) or [a-z-]{4,} ', r' \1 '),
    (r'  +', ' '),
))
verbbracketscleaner = ReplacementListCompiler ((
    (r'\(([^()]+?)(,| or) [^()]+\)', r'\1'), # retain only the first item in brackets
    (r'[()]', ''), # remove brackets
))
verbcleaner = ReplacementListCompiler ((
    (r', to .*$', ' '),
    (r',? (so as to|in order to|as by|as if|by means of|so that) .*$', ' '),
    (r'^(to [a-z ]+), ([a-z-]+|[a-z-]+, [a-z-]+|[a-z-]+, [a-z-]+, [a-z-]+) *$', r'\1 '),
    (r'^(to [a-z-]+) (and|or) [a-z-]+ ' + phrasals + ' ', r'\1 \3 '),
    (r'^(to [a-z-]+), ([a-z-]+|[a-z-]+, [a-z-]+|[a-z-]+, or [a-z-]+) ' + phrasals + ' *$', r'\1 '),
    (r'^(to [a-z-]+), ([a-z-]+|[a-z-]+, [a-z-]+|[a-z-]+, or [a-z-]+) (' + phrasals + ' [a-z-]+)', r'\1 \3'),
    (r', [a-z-]+, or [a-z-]+ *$', ' '),
    (r',? or [a-z-]+ *$', ' '),
    (r'(, [a-z-]+){1,5} *$', ' '),
    (r'^(to [a-z-]+) or [a-z-]+ ([a-z-]+) *$', r'\1 \2 '),
    (r'^(to [a-z-]+), (make|be|become) [a-z-]+ *$', r'\1 '),
    (r' (supply|provide|furnish) with([, ])', r' provide with\2'),
    (r' (in|into|inside|within)([, ])', r' in\2'),
    (r' (on|onto|upon)([, ])', r' on\2'),
    (r' (a|an|the|its|one\'s|some|their|one) ', ' '),
    (r' (a|an|the|its|one\'s|some|their|one) ', ' '),
))

useless_tails = set(('of', 'to', 'from', 'by', 'with', 'for', 'in', 'at',
    'away', 'than', 'when', 'again'))


def gloss_normalizer(gloss, wordclass):
    """Normalizes the gloss, and removes extraneous elements. Mainly
    for producing a version of the gloss from which a usable superordinate
    can be extracted
    """
    if not gloss:
        return ''
    else:
        gnormal = gloss
        # Decapitalize
        if len(gnormal) > 1:
            gnormal = gnormal[0].lower() + gnormal[1:]
        # Remove extraneous stuff
        if wordclass == 'VB':
            gnormal = verbbracketscleaner.edit(' %s ' % gnormal).strip()
        gnormal = glossnormal.edit(' %s ' % gnormal).strip()

        if wordclass == 'VB':
            if not gnormal.strip().startswith('to '):
                return ''
            else:
                gnormal = verb_normalizer(gnormal)
        return gnormal.strip() + ' '


def verb_normalizer(gloss):
    gloss = verbcleaner.edit(gloss.strip() + ' ').strip()
    tokens = gloss.split(' ')
    if len(tokens) > 4:
        part1 = ' '.join(tokens[:3])
        part2 = ' '.join(tokens[3:])
        part2 = re.sub('([,:;]| and | or ).*$', '', ' ' + part2 + ' ')
        part2 = re.sub(' (by|with|for|in|on|which|who|as) .*$', '', ' ' + part2 + ' ')
        if part1.endswith(','):
            gloss = part1
        else:
            gloss = ' '.join((part1.strip(), part2.strip(),))
    gloss = gloss.strip(', ')
    gloss = re.sub(r', [a-z-]+ *$', '', gloss)

    tokens = [t.strip() for t in gloss.split(' ')]
    while len(tokens) > 3 and tokens[-1] in useless_tails:
        tokens.pop()
    return ' '.join(tokens[0:5])

