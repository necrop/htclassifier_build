import re

from stringtools import porter_stem
from regexcompiler import ReplacementListCompiler

LIGHT_STEMMER = ReplacementListCompiler((
    (r'(y|ies|ie)$', r'i'),
    (r'sses$', r'ss'),
    (r'([^s])s$', r'\1'),
))


def lemma_components(sense, etyma):
    etyma = [etymon.lemma for etymon in etyma
             if etymon.language == 'English' and
             not etymon.lemma_manager().is_affix()]

    components = []
    if not ' ' in sense.lemma and not '-' in sense.lemma:
        components.append(sense.lemma)

    if not sense.is_derivative():
        components = [re.sub(r'(.)\'s$', r'\1', w).strip().lower()
                      for w in sense.lemma_manager().decompose(base=sense.lemma)]
    components.extend(etyma)

    # Add in the entry headword. This will be overkill in most cases -
    #  except for the case of derivatives, the headword should already
    #  be included by virtue of decompose() above - but will cover the
    #  occasional cases where a compound has not been decomposed
    #  correctly
    if not sense.headword_manager().is_affix():
        components.append(sense.headword_manager().lemma)

    # Remove junk
    components = [w.lower() for w in components if len(w) >= 3
                  and w.lower() not in ('the', 'and')]

    # Porter-stem, so as to align with other definition keywords
    return [porter_stem(w) for w in components]


def compound_components(sense, etyma):
    elements = []

    # Break into ordered components (components which we can reliably
    #  identify as 'first' or 'last')
    ordered_elements = []
    if sense.is_subentry() and not sense.is_derivative():
        ordered_elements = sense.lemma_manager().decompose(base=sense.headword,
                                                           break_affix=True)
    elif not sense.is_subentry():
        ordered_elements = sense.lemma_manager().decompose(base=sense.headword)
        if (len(ordered_elements) == 1 and
                len(etyma) == 2 and
                not etyma[0].lemma_manager().is_affix() and
                not etyma[1].lemma_manager().is_affix()):
            ordered_elements = []
            for etymon in etyma:
                if etymon.language == 'English':
                    ordered_elements.append(etymon.lemma)
                else:
                     # Add dummy value to maintain correct index positions;
                     #  these will be omitted because they'll fail the
                     #  'len(x) >= 3' test below
                    ordered_elements.append('')

    if len(ordered_elements) >= 2:
        ordered_elements = [re.sub(r'(.)\'s$', r'\1', c).strip().lower()
                            for c in ordered_elements]
        # Note that we use the light_stemmer, not the much more aggressive
        #   Porter stemmer. This is because e.g. 'fish' and 'fishing' are
        #   very different in the context of a compound lemma
        ordered_elements = [LIGHT_STEMMER.edit(c) for c in ordered_elements]
        if len(ordered_elements[0]) >= 3:
            elements.append(ordered_elements[0] + '_FIRST')
        if len(ordered_elements[-1]) >= 3:
            elements.append(ordered_elements[-1] + '_LAST')

    # Extend this with a grab-bag of unordered components (using
    #  lemma_components() above). These *will* be Porter-stemmed
    orderless_elements = lemma_components(sense, etyma)
    elements.extend(set([c[0:8] for c in orderless_elements]))

    # Tidy up
    elements = [e.replace(' ', '').replace('-', '') for e in elements]
    return elements
