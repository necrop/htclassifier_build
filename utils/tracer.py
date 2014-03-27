import lex.oed.thesaurus.thesaurusdb as tdb


def trace_sense(sense):
    lines = ['--------------------------------------------------',]
    lines.append('"%s" %s  (%d#eid%d)' % (sense.lemma, sense.wordclass,
        sense.entry_id, sense.node_id))
    lines.append('"%s"' % sense.definition)
    lines.append('"%s"' % sense.gloss)
    if sense.subjects:
        lines.append('subjects: ' + ', '.join(['"%s"' % s for s in sense.subjects]))
    if sense.etyma:
        lines.append('etyma: ' + ', '.join(['"%s"' % e[0] for e in sense.etyma]))

    try:
        sense.superordinate
    except AttributeError:
        pass
    else:
        if sense.superordinate:
            lines.append('superordinate: %s  (%s)' % (
                sense.superordinate, sense.superordinate_full))

    try:
        sense.synonyms
    except AttributeError:
        pass
    else:
        if sense.synonyms:
            lines.append('synonyms:' + ', '.join(['"%s"' % s
                for s in sense.synonyms]))

    try:
        sense.noun_phrases
    except AttributeError:
        pass
    else:
        if sense.noun_phrases:
            lines.append('NPs:' + ', '.join(['"%s"' % np for np in
                sense.noun_phrases]))

    try:
        sense.bayes
    except AttributeError:
        pass
    else:
        for thesclass in sense.bayes.branches(max_delta=0.3):
            lines.append('Bayes: %s' % thesclass.breadcrumb())

    try:
        sense.class_id
    except AttributeError:
        pass
    else:
        thesclass = tdb.get_thesclass(sense.class_id)
        lines.append('>>>')
        lines.append(trace_class(thesclass))

        try:
            sense.reason_code
        except AttributeError:
            pass
        else:
            if sense.reason_code is not None:
                lines.append('Reason code: %s' % sense.reason_code)

        try:
            sense.reason_text
        except AttributeError:
            pass
        else:
            if sense.reason_text is not None:
                lines.append('Reason: %s' % sense.reason_text)

    lines = [simples.sub('?', l) for l in lines]
    return '\n\t'.join(lines)


def trace_instance(instance):
    lines = []
    lines.append('"%s" (%d#eid%d) rating=%.3g' % (instance.lemma,
        instance.refentry, instance.refid, instance.rating()))
    lines.append('sense size: %.3g  |  entry size: %.3g' % (instance.size,
        instance.entry_size))
    if instance.thesclass is not None:
        lines.append(trace_class(instance.thesclass))
    else:
        lines.append('[none]')
    return '\n\t'.join(lines)


def trace_class(thesclass):
    lines = []
    lines.append('%d: %s  (b=%d n=%d)' % (thesclass.id, thesclass.breadcrumb(),
        thesclass.branch_size, thesclass.node_size))
    return '\n\t'.join(lines)
