"""Transparent, deterministic revision rules derived from the learner's quiz history."""
from datetime import datetime, timedelta, timezone

LEVELS = ['Foundational', 'Intermediate', 'Advanced']
INTERVALS = [1, 3, 7, 14, 30]

def revision_plan(kit, history, at=None):
    at = at or datetime.now(timezone.utc)
    topics = list(dict.fromkeys([q['topic'] for q in kit.get('questions',[])] + [f['topic'] for f in kit['facts']] + [r['topic'] for a in history if a['kitId']==kit['id'] for r in a['results']]))
    rows = []
    for topic in topics:
        difficulty, streak, reviewed, mistakes = 0, 0, 0, 0
        due, last_score, interval = at, None, 0
        reason = 'Take a first recall check to establish your starting point.'
        last_review = None
        for attempt in sorted(history, key=lambda a:a['date']):
            if attempt['kitId'] != kit['id']:continue
            answers = [r for r in attempt['results'] if r['topic'] == topic]
            if not answers:continue
            stamp = datetime.fromisoformat(attempt['date'].replace('Z','+00:00'))
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            correct = sum(bool(r['correct']) for r in answers)
            last_score = round(100 * correct / len(answers))
            mistakes += len(answers)-correct
            reviewed += 1
            # Early successes do not accelerate the spaced schedule.
            early = last_review is not None and stamp < due
            if last_score < 70:
                difficulty=max(0,difficulty-1);streak=0;interval=0
                due=stamp+timedelta(minutes=10)
                reason='Recent mistakes: step down, review the explanation, then retry in 10 minutes.'
            elif not early:
                if last_score >= 85:
                    streak+=1;difficulty=min(2,difficulty+1)
                    interval=INTERVALS[min(streak-1,len(INTERVALS)-1)]
                    reason='Strong recall: increase challenge and extend the review interval.'
                else:
                    streak=0;interval=1
                    reason='Mixed recall: keep this difficulty and review tomorrow.'
                due=stamp+timedelta(days=interval)
            else:
                reason='Early practice completed. Your existing review date stays unchanged.'
            last_review=stamp
        rows.append({'topic':topic,'difficulty':LEVELS[difficulty],'streak':streak,
            'reviews':reviewed,'mistakes':mistakes,'lastScore':last_score,
            'dueAt':due.isoformat(),'due':due<=at,'intervalDays':interval,'reason':reason})
    rows.sort(key=lambda r:(not r['due'],r['dueAt'],-r['mistakes']))
    return {'kitId':kit['id'],'topics':rows,'dueCount':sum(r['due'] for r in rows),
        'generatedAt':at.isoformat(),'method':'Mistakes → 10 minutes; successful due reviews → 1, 3, 7, 14, 30 days. Early successes do not extend the interval.'}
