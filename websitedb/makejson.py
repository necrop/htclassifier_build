
import os
import string
import random
import json
from collections import defaultdict

from stringtools import lexical_sort
from pickler.sensemanager import PickleLoader
import lex.oed.thesaurus.thesaurusdb as tdb


TRIAGE = ('classified', 'unclassified', 'intractable')
LETTERS = string.ascii_uppercase

FIELDS = {
    'sense': [
        'status',
        'lemma',
        'lemmasort',
        'wordclass',
        'definition',
        'definition_supplement',
        'refentry',
        'refid',
        'headword',
        'headwordsort',
        'subentrytype',
        'undefined',
        'sampleorder',
        'bayes_id',
        'bayesconfidence',
        'bayesmismatch',
        'thesclass1_id',
        'thesclass2_id',
        'thesclass3_id',
        'checkbox1',
        'checkbox2',
        'checkbox3',
        'checkstatus',
        'level2branch_id',
        'reasontext',
        'reasoncode',
        'splitdefinition',
    ],
    'thesaurusclass': [
        'id',
        'label',
        'wordclass',
        'level',
        'branchsize',
        'sortcode',
        'superordinate_id',
    ],
}

STATUS_INDEX = FIELDS['sense'].index('status')
THESCLASS_INDEX = FIELDS['sense'].index('thesclass1_id')
REASONCODE_INDEX = FIELDS['sense'].index('reasoncode')


def populate_taxonomy(**kwargs):
    out_dir = kwargs.get('out_dir')

    outfile = os.path.join(out_dir, 'taxonomy.json')
    with open(outfile, 'w') as filehandle:
        for c in tdb.taxonomy():
            row = (c.id, c.label, c.wordclass, c.level, c.branch_size, c.sortcode, c.parent_id)
            data = {fieldname: value for fieldname, value in
                    zip(FIELDS['thesaurusclass'], row)}
            filehandle.write(json.dumps(data))
            filehandle.write('\n')


def populate_senses(**kwargs):
    input = kwargs.get('input')
    out_dir = kwargs.get('out_dir')

    for letter in LETTERS:
        data = defaultdict(list)
        for parent_dir in input:
            for t in TRIAGE:
                if t == 'unclassified' and 'iteration1' in parent_dir:
                    continue

                if t == 'classified':
                    status = '1'
                elif t == 'unclassified':
                    status = '0'
                elif t == 'intractable':
                    status = 'n'

                dir = os.path.join(parent_dir, t)
                pl = PickleLoader(dir, letters=letter)
                for sense in pl.iterate():
                    row = _sense_to_row(sense, status)
                    signature = (sense.entry_id, sense.node_id,)
                    data[signature].append(row)

        output = []
        for rows in data.values():
            # Where there are multiple rows for a single sense,
            #  we compare them to decide which are worth keeping
            if len(rows) > 1:
                rows = _compare_cloned_senses(rows)
            # Change clone_num to True/False
            for row in rows:
                if row[-1] == 0:
                    row[-1] = False
                else:
                    row[-1] = True
            # Append to the output that's going to be committed to
            #  the database
            for row in rows:
                output.append(row)

        outfile = os.path.join(out_dir, letter + '.json')
        with open(outfile, 'w') as filehandle:
            for row in output:
                data = {fieldname: value for fieldname, value in
                        zip(FIELDS['sense'], row)}
                filehandle.write(json.dumps(data))
                filehandle.write('\n')


def _sense_to_row(sense, status):
    if sense.definition is None:
        undefined = True
        definition = None
    else:
        undefined = False
        definition = sense.definition[:200]

    if sense.definition_supplement:
        definition_supplement = sense.definition_supplement[:150]
    else:
        definition_supplement = None

    try:
        reasoncode = sense.reason_code
    except AttributeError:
        reasoncode = None
    try:
        reasontext = sense.reason_text[:200]
    except (AttributeError, TypeError):
        reasontext = None

    try:
        thesclass1_id = sense.class_id
    except AttributeError:
        thesclass1_id = None
    try:
        thesclass2_id = sense.runners_up[0]
    except (AttributeError, IndexError):
        thesclass2_id = None
    try:
        thesclass3_id = sense.runners_up[1]
    except (AttributeError, IndexError):
        thesclass3_id = None

    if thesclass1_id is not None:
        thesclass = tdb.get_thesclass(thesclass1_id)
        level2branch = thesclass.ancestor(level=2)
        checkstatus = 'u'
    else:
        level2branch = None
        checkstatus = 'n'

    if level2branch is not None:
        level2branch_id = level2branch.id
    else:
        level2branch_id = None

    try:
        bayes = sense.bayes_classification
        bayes_confidence = sense.bayes_confidence
    except AttributeError:
        bayes = None
        bayes_confidence = 0

    row = [
        status,
        sense.lemma[:100],
        lexical_sort(sense.lemma)[:100],
        sense.wordclass or 'NN',
        definition,
        definition_supplement,
        sense.entry_id,
        sense.node_id,
        sense.entry_lemma[:50],
        lexical_sort(sense.entry_lemma)[:50],
        sense.subentry_type or 'main sense',
        undefined,
        random.randint(0, 10000),  # sample order
        bayes,
        bayes_confidence,
        _bayes_mismatch(sense),
        thesclass1_id,
        thesclass2_id,
        thesclass3_id,
        'u',  # checkbox for thesclass1 (unset)
        'i',  # checkbox for thesclass2 (incorrect)
        'i',  # checkbox for thesclass3 (incorrect)
        checkstatus,
        level2branch_id,
        reasontext,
        reasoncode,
        sense.clone_num,  # Gets changed to True/False before committing to DB
    ]
    return row


def _compare_cloned_senses(rows):
    """
    Compare multiple rows for the same sense, to decide which are worth
    keeping.

    - clone_num=0 is the full sense;
    - clone_num=1, clone_num=2, etc., are subdefinitions.
    (clone_num is the last element in the row, i.e. at index -1)

    If any of the subdefinition clones have failed, we discard them and
    use the full sense.

    If the subdefinition clones have come to the same conclusion as the
    full sense, we discard them and use the full sense.

    Returns a list of one or more rows.
    """
    # Sort by clone_num value (so that the first is first, whatever its
    #  status classification)
    rows.sort(key=lambda r: r[-1])
    full_sense = rows.pop(0)

    # Ditch any clones with '0' or 'n' status
    rows = [r for r in rows if r[STATUS_INDEX] == '1']

    # Drop rows that just duplicate the same thesaurus class ID
    seen = set()
    rows2 = []
    for row in rows:
        class_id = row[THESCLASS_INDEX]
        if not class_id in seen:
            rows2.append(row)
            seen.add(class_id)
    rows = rows2

    # Drop rows that are just Bayes-/topic-based (if one of the rows has
    #  something better)
    rows = [r for r in rows if r[REASONCODE_INDEX] != 'topc'] or rows

    # If all that leaves none or only one subdefinition, we forget about them
    #  and just return the full sense.
    if len(rows) <= 1:
        return [full_sense,]
    else:
        return rows


def _bayes_mismatch(sense):
    try:
        sense.bayes_classification
    except AttributeError:
        return False
    try:
        sense.class_id
    except AttributeError:
        return False

    if (sense.class_id is None or
            sense.bayes_classification is None or
            sense.bayes_confidence <= 3):
        return False

    selected_class = tdb.get_thesclass(sense.class_id)
    bayes_class = tdb.get_thesclass(sense.bayes_classification)
    if bayes_class.level > 3:
        bayes_class = bayes_class.ancestor(level=3)
    if selected_class.is_descendant_of(bayes_class):
        return False
    else:
        return True
