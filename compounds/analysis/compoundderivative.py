
import lex.oed.thesaurus.thesaurusdb as tdb

derivation_forms = (
    ('ism', ('NN',), ''),
    ('ist', ('NN', 'JJ',), ''),
    ('ism', ('NN',), 'ist'),
    ('ist', ('NN', 'JJ',), 'ism'),
    ('logism', ('NN',), 'logy'),
    ('logist', ('NN', 'JJ',), 'logy'),
    ('ical', ('JJ',), 'ic'),
    ('logical', ('JJ',), 'logy'),
    ('ily', ('RB',), 'y'),
    ('ly', ('RB',), ''),
    ('ied', ('JJ',), 'y'),
    ('ed', ('JJ',), ''),
    ('ed', ('JJ',), 'e'),
    ('ing', ('JJ', 'NN'), ''),
    ('ing', ('JJ', 'NN'), 'e'),

    ('ed', ('JJ',), 'ing'),
    ('ing', ('JJ', 'NN'), 'ed'),

    ('ship', ('NN',), ''),
    ('ness', ('NN',), ''),
    ('iness', ('NN',), 'y'),
    ('hood', ('NN',), ''),
    ('dom', ('NN',), ''),
    ('ful', ('JJ',), ''),
)

colours = {'black', 'blue', 'yellow', 'brown', 'red', 'white', 'green',
           'orange', 'pink', 'purple', 'grey', 'gray'}


def compound_derivative(sense):
    if sense.last_element() is None:
        return None, None

    thesclass = None
    for ending, wordclasses, replacement in derivation_forms:
        if (sense.wordclass in wordclasses and
            sense.last_element().endswith(ending) and
            len(sense.last_element()) > len(ending) + 2):

            # Figure out what the base form would look like,
            #  if the lemma *is* a derivative
            # - Strip off the ending, then add the replacement ending
            #  (which is usually a null string).
            hypothetical_base =\
                sense.lemma[0:len(sense.lemma)-len(ending)] + replacement

            # Test if the hypothetical base form exists, and if so
            #  find out how it is classified
            base_classifications = tdb.ranked_search(lemma=hypothetical_base,
                                                     current_only=True)

            if (tdb.distinct_senses(base_classifications) == 1 and
                    base_classifications[0].thesclass is not None):
                thesclass = base_classifications[0].thesclass
                break

    if thesclass is not None:
        # Don't risk things like 'yellow-bellied' - these are
        #  likely to be transparent, not a derivative of e.g.
        #  'yellow-belly', so should go after existing guesses
        if ending in ('ed', 'ied') and sense.first_element().lower() in colours:
            position = 'last'
        else:
            position = 'first'
        return base_classifications[0].thesclass, position
    else:
        return None, None
