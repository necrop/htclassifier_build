
import re

from regexcompiler import ReplacementListCompiler
import lex.oed.thesaurus.thesaurusdb as tdb
from utils.tracer import trace_sense

definition_preparer = ReplacementListCompiler((
    (r'\([^()]+\)', ''),  # Remove anything in parentheses
    (r'^(trans|intr)\. and (trans|intr)\. *', ''),
    (r'^(intr|trans|refl)\. *', ''),
    (r'\. (Obs|rare|Now rare|Obs. *rare)\.$', r'.'),
    (r'Of [^:]+:', ''),
    (r'([^a-z])(very|highly|somewhat|rather|particularly|extremely) ', r'\1 '),
    (r'(Very|Highly|Somewhat|Rather|Particularly|Extremely) ', r' '),
    (r'^[A-Z][a-z]+\. ([A-Z][a-z])', r'\1'),  # Remove label at the start
    (r', etc\.', ''),
    (r' spec\.', ' '),
    (r', or ', ', '),
    (r':', ';'),
    (r'  +', ' '),
))

vb_regex = '([a-z]+|[a-z]+ (on|off|up|down|in|out|for|by|away|against|with|together|apart|back))'

synfinders = {
    'NN': [
        (r'; (a|an) ([a-z]+|[a-z]+-[a-z]+), ([a-z]+|[a-z]+[ -][a-z]+), (or |)([a-z]+|[a-z]+-[a-z]+)(;|\.$|\. [A-Z])', [2, 3, 5,], 'definition'),
        (r'; ([a-z]+|[a-z]+[ -][a-z]+), ([a-z]+|[a-z]+[ -][a-z]+), (or |)([a-z]+|[a-z]+-[a-z]+)(;|\.$|\. [A-Z])', [1, 2, 4,], 'definition'),
        (r'; (a|an|the) ([a-z]+|[a-z]+-[a-z]+) or ([a-z]+|[a-z]+-[a-z]+)(;|\.$|\. [A-Z])', [2, 3,], 'definition'),
        (r'; (a|an) ([a-z]+|[a-z]+[ -][a-z]+), (a|an) ([a-z]+|[a-z]+[ -][a-z]+)(;|\.$|\. [A-Z])', [2, 4,], 'definition'),
        (r'; (a|an|the) ([a-z]+|[a-z]+[ -][a-z]+)(;|\.$|\. [A-Z])', [2,], 'definition'),
        (r'^; ([a-z]+|[a-z]+[ -][a-z]+)\.$', [1,], 'definition'),
        (r'^; ([a-z]+|[a-z]+[ -][a-z]+)[;,] ([a-z]+|[a-z]+[ -][a-z]+)\.$', [1, 2,], 'definition'),
        (r'^; ([a-z]+|[a-z]+-[a-z]+) or ([a-z]+|[a-z]+-[a-z]+)\.$', [1, 2,], 'definition'),
        (r'^; ([a-z]+[ -][a-z]+) or ([a-z]+[ -][a-z]+)\.$', [1, 2,], 'definition'),
        (r'^; (a|an|the) ([a-z]+|[a-z]+-[a-z]+); (a|an|the) ([a-z]+|[a-z]+-[a-z]+)\.$', [2, 4,], 'definition'),
        (r'^; [a-z ,-]+; ([a-z]+)\.$', [1,], 'definition'),
        (r'^; [a-z ,-]+; ([a-z]+), ([a-z]+)\.$', [1, 2,], 'definition'),
        (r'^(a|an|the) ([a-z]+|[a-z]+[ -][a-z]+)$', [2,], 'gloss'),
        (r'^a (kind|type|variety) of ([a-z]+|[a-z]+[ -][a-z]+)$', [2,], 'gloss'),
        (r'^([a-z]+|[a-z]+[ -][a-z]+)$', [1,], 'gloss'),
        (r'^(a|an) [a-z -]+, (a|an) ([a-z]+|[a-z]+[ -][a-z]+)$', [3,], 'gloss'),
        (r'^the [a-z -]+, the ([a-z]+|[a-z]+[ -][a-z]+)$', [1,], 'gloss'),
        (r'^([a-z]+), ([a-z]+)$', [1, 2,], 'gloss'),
    ],
    'JJ': [
        (r'; ([a-z]+|[a-z]+-[a-z]+)[;,] ([a-z]+|[a-z]+-[a-z]+)[;,] ([a-z]+|[a-z]+-[a-z]+)[;,] ([a-z]+|[a-z]+-[a-z]+)(;|\.$|\. [A-Z])', [1, 2, 3, 4,], 'definition'),
        (r'; ([a-z]+|[a-z]+-[a-z]+)[;,] ([a-z]+|[a-z]+-[a-z]+)[;,] ([a-z]+|[a-z]+-[a-z]+)(;|\.$|\. [A-Z])', [1, 2, 3,], 'definition'),
        (r'; ([a-z]+|[a-z]+-[a-z]+)(,|;| or) ([a-z]+|[a-z]+-[a-z]+)(;|\.$)', [1, 3,], 'definition'),
        (r'^([a-z]+|[a-z]+-[a-z]+)$', [1,], 'gloss'),
        (r'^([a-z]+), ([a-z]+)$', [1, 2,], 'gloss'),
    ],
    'RB': [
        # Re-use all the JJ models first
        (r'; (([a-z]+|[a-z]+-[a-z]+)ly)(,|;| or |\.$|\. [A-Z])', [1,], 'definition'),
        (r', (([a-z]+|[a-z]+-[a-z]+)ly)(;|\.$|\. [A-Z])', [1,], 'definition'),
    ],
    'VB': [
        (r'; to %s, %s, (or |)%s(;|\.$|\. [A-Z])' % (vb_regex, vb_regex, vb_regex), [1, 3, 6,], 'definition'),
        (r'; to ([a-z]+) or (to |)%s(;|\.$|\. [A-Z])' % (vb_regex,), [1, 3,], 'definition'),
        (r'; to %s[;,] to %s(;|\.$|\. [A-Z])' % (vb_regex, vb_regex), [1, 3,], 'definition'),
        (r'; to %s(;|\.$|\. [A-Z])' % (vb_regex,), [1,], 'definition'),
        (r'^to %s$' % (vb_regex,), [1,], 'gloss'),
        (r'^to ([a-z]+), ([a-z]+)$', [1, 2,], 'gloss'),
    ]
}
# Compile the regular expressions
for wordclass, tuplist in synfinders.items():
    tuplist = [(re.compile(t[0]), t[1], t[2]) for t in tuplist]
    synfinders[wordclass] = tuplist


def locate_synonyms(sense):
    definition = sense.definition
    gloss = re.sub(r'(very|somewhat|rather|particularly|extremely) ', r'\1', sense.gloss)
    wordclass = sense.wordclass

    if definition is None:
        definition = ''
    if gloss is None:
        gloss = ''
    gloss = _decapitalize(gloss)

    d = definition_preparer.edit(definition).strip()
    d = _decapitalize(d)
    # Add semi-colon + space at the beginning, so that regexes don't need to
    #  handle the start of the string in any special way
    d = '; ' + d

    synonyms = []
    if wordclass in ('NN', 'JJ', 'VB', 'RB'):
        if wordclass == 'RB':
            regexes = synfinders['JJ'] + synfinders['RB']
        else:
            regexes = synfinders[wordclass]
        for regex, groups, texttype in regexes:
            if texttype == 'definition':
                m = regex.search(d)
            elif texttype == 'gloss':
                m = regex.search(gloss)
            if m is not None:
                for g in groups:
                    synonyms.append(m.group(g))
                break
    elif wordclass == 'UH':
        m = re.findall('\u2018(.*?)\u2019', definition)
        if m is not None:
            synonyms = [s.lower().strip('!') for s in m]

    # Clean up the synonyms
    synonyms = [s.strip(';, !') for s in synonyms]
    synonyms = [re.sub(r'^(a|an|the) ', '', s) for s in synonyms]
    synonyms = [s for s in synonyms if len(s) > 2 and
                s not in ('and', 'but', 'the', 'for', 'with', 'from', 'fig')]

    # Test any 2-gram synonyms
    synonyms2 = []
    for s in synonyms:
        if ' ' in s and is_valid_bigram(s, wordclass):
            if wordclass == 'VB':
                synonyms2.append('to ' + s)
            else:
                synonyms2.append(s)
        elif not ' ' in s:
            synonyms2.append(s)

    return synonyms2


def is_valid_bigram(bigram, wordclass):
    # Verb bigrams will only be phrasal verbs, so need to have 'to' prepended
    if wordclass == 'VB':
        bigram = 'to ' + bigram
        z = tdb.search(lemma=bigram)
    else:
        z = tdb.search(lemma=bigram, wordclass=wordclass)
    if z:
        return True
    else:
        return False


def _decapitalize(text):
    if len(text) > 1:
        text = text[0].lower() + text[1:]
    text = text.replace(' A ', ' a ').replace(' An ', ' an ')\
        .replace(' The ', ' the ')
    return text
