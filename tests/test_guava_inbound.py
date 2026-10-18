from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from dock_intake.guava_inbound import build_agent, serve


class FakeAgent:
    def __init__(self, **kwargs):
        self.handlers = {}
        self.transports = []

    def on_call_start(self, fn):
        self.handlers['start'] = fn
        return fn

    def on_task_complete(self, fn):
        self.handlers['complete'] = fn
        return fn

    def on_question(self, fn):
        self.handlers['question'] = fn
        return fn

    def on_session_end(self, fn):
        self.handlers['end'] = fn
        return fn

    def listen_phone(self, number):
        self.transports.append(('phone', number))

    def listen_webrtc(self, code):
        self.transports.append(('webrtc', code))


class FakeCall:
    id = 'session-offline'

    def __init__(self):
        self.variables = {}
        self.fields = {}
        self.instructions = []
        self.infos = []
        self.retries = []

    def set_variable(self, key, value):
        self.variables[key] = value

    def get_variable(self, key, default=None):
        return self.variables.get(key, default)

    def get_field(self, key):
        return self.fields.get(key)

    def set_task(self, task_id, **kwargs):
        self.task_id = task_id
        self.task = kwargs

    def set_language_mode(self, **kwargs):
        self.language = kwargs

    def send_instruction(self, text):
        self.instructions.append(text)

    def add_info(self, label, info):
        self.infos.append((label, info))

    def retry_task(self, reason):
        self.retries.append(reason)

    def hangup(self, instructions):
        self.instructions.append(instructions)


class FakeSession:
    as_of = datetime(2026, 10, 17, 19, 36, tzinfo=timezone.utc)

    def __init__(self):
        self.reports = []
        self.error = None

    def status(self, load):
        return {'load_id': load, 'known': load == 'LL-88421', 'eta': None, 'stage': 'waiting'}

    def report(self, load, **kwargs):
        if self.error:
            raise self.error
        self.reports.append((load, kwargs))
        return {'saved': True, 'event_id': 'test-event', 'status': self.status(load)}


def setup():
    session = FakeSession()
    agent = build_agent(session, sdk=SimpleNamespace(Agent=FakeAgent, Field=lambda **kw: kw))
    call = FakeCall()
    agent.handlers['start'](call)
    return session, agent, call


def complete(agent, call, **fields):
    task_id = call.task_id
    call.fields.update({f'{task_id}_{key}': value for key, value in fields.items()})
    agent.handlers['complete'](call, task_id)
    return task_id


def begin_report(agent, call, **fields):
    complete(agent, call, load='LL-88421')
    complete(agent, call, action='report')
    return complete(agent, call, state=fields.get('state', 'waiting'), detail=fields.get('detail', 'They have not started unloading.'), time=fields.get('time', 'now'), expected=fields.get('expected', 'in 20 minutes'))


def test_status_questions_and_abandoned_report_never_write():
    session, agent, call = setup()
    assert 'load number first' in agent.handlers['question'](call, 'Where is it?')
    complete(agent, call, load='LL-88421')
    assert '"eta": null' in agent.handlers['question'](call, 'Where is it?')
    complete(agent, call, action='report')
    complete(agent, call, state='waiting', detail='Not yet started', time='now')
    agent.handlers['end'](call, None)
    assert session.reports == []


def test_explicit_readback_confirmation_and_stable_identity():
    session, agent, call = setup()
    report_task = begin_report(agent, call)
    assert session.reports == []
    confirm_task = complete(agent, call, confirmation='yes')
    assert len(session.reports) == 1
    load, report = session.reports[0]
    assert load == 'LL-88421'
    assert report['state'] == 'waiting'
    assert report['expected_start'] == 'in 20 minutes'
    assert report['occurred_at'] == session.as_of
    assert report['action_id'] == f'{call.id}:{report_task}'
    agent.handlers['complete'](call, confirm_task)
    assert len(session.reports) == 1
    # A new report gets new field names; old yes is not read as confirmation.
    complete(agent, call, action='report')
    complete(agent, call, state='unloading_started', detail='Actual unloading now', time='now')
    complete(agent, call)
    assert len(session.reports) == 1


def test_unknown_load_does_not_assume_demo_load():
    session, agent, call = setup()
    complete(agent, call, load='UNKNOWN')
    assert call.retries
    assert call.get_variable('dock_load') is None
    assert session.reports == []


@pytest.mark.parametrize('confirmation', ['no', None, 'true'])
def test_unconfirmed_report_is_not_saved(confirmation):
    session, agent, call = setup()
    begin_report(agent, call)
    complete(agent, call, confirmation=confirmation)
    assert session.reports == []


def test_storage_failure_does_not_claim_saved():
    session, agent, call = setup()
    begin_report(agent, call)
    session.error = OSError('private filesystem information')
    complete(agent, call, confirmation='yes')
    assert ('Report failure', {'saved': False, 'reason': 'Storage unavailable'}) in call.infos
    assert not any(label == 'Persistence result' for label, _ in call.infos)
    assert session.reports == []


def test_transit_report_and_ambiguous_time_do_not_write():
    session, agent, call = setup()
    begin_report(agent, call, state='outside_scope', detail='Traffic jam')
    assert call.task_id.startswith('offer_')
    assert session.reports == []
    complete(agent, call, action='report')
    complete(agent, call, state='unloading_started', time='yesterday', detail='started yesterday')
    assert call.retries
    assert session.reports == []


def test_inbound_gate_is_separate_from_outbound_gate(monkeypatch):
    monkeypatch.delenv('DOCK_INBOUND_MODE', raising=False)
    monkeypatch.setenv('DOCK_CALL_MODE', 'live')
    with pytest.raises(RuntimeError, match='DOCK_INBOUND_MODE'):
        serve(FakeSession())


def test_live_phone_requires_number_before_sdk_import(monkeypatch):
    monkeypatch.setenv('DOCK_INBOUND_MODE', 'live')
    monkeypatch.delenv('GUAVA_AGENT_NUMBER', raising=False)
    with pytest.raises(RuntimeError, match='GUAVA_AGENT_NUMBER'):
        serve(FakeSession())


def test_transport_registration_with_fake_sdk_only(monkeypatch):
    monkeypatch.setenv('DOCK_INBOUND_MODE', 'live')
    created = []
    def factory(**kwargs):
        agent = FakeAgent(**kwargs)
        created.append(agent)
        return agent
    sdk = SimpleNamespace(Agent=factory, Field=lambda **kw: kw)
    serve(FakeSession(), transport='webrtc', webrtc_code='offline-test', sdk=sdk)
    assert created[0].transports == [('webrtc', 'offline-test')]


def test_change_load_drops_prior_load_before_new_lookup():
    session, agent, call = setup()
    complete(agent, call, load='LL-88421')
    complete(agent, call, action='change_load')
    assert call.get_variable('dock_load') is None
    complete(agent, call, load='UNKNOWN')
    assert call.get_variable('dock_load') is None
    assert 'load number first' in agent.handlers['question'](call, 'Where is it?')
    assert session.reports == []


def test_confirmed_report_survives_next_call_and_restart(root, tmp_path):
    from dock_intake.session import InboundSession
    log = tmp_path / 'runtime.jsonl'
    session = InboundSession(root, log, FakeSession.as_of)
    sdk = SimpleNamespace(Agent=FakeAgent, Field=lambda **kw: kw)
    agent = build_agent(session, sdk=sdk)
    call = FakeCall()
    agent.handlers['start'](call)
    begin_report(agent, call, state='unloading_started', detail='Unload actually began now', expected='')
    complete(agent, call, confirmation='yes')
    restarted = InboundSession(root, log, FakeSession.as_of)
    second_agent = build_agent(restarted, sdk=sdk)
    second_call = FakeCall()
    second_agent.handlers['start'](second_call)
    complete(second_agent, second_call, load='LL-88421')
    statuses = [info for label, info in second_call.infos if label == 'Shipment status']
    assert statuses[-1]['stage'] == 'unloading_started'
    assert statuses[-1]['clock']['phase'] == 'closed'
    assert statuses[-1]['clock']['estimated_charge_usd'] == '0.00'


def test_question_read_failure_returns_unavailable():
    session, agent, call = setup()
    complete(agent, call, load='LL-88421')
    def broken(load):
        raise OSError('private filesystem detail')
    session.status = broken
    answer = agent.handlers['question'](call, 'Current status?')
    assert 'unavailable' in answer
    assert 'private filesystem' not in answer


class FakeHandoff:
    def __init__(self, status='disabled'):
        self.status = status
        self.calls = []

    def request(self, call):
        self.calls.append(call.id)
        return {'status': self.status}


def handoff_setup(status='disabled'):
    session = FakeSession()
    gate = FakeHandoff(status)
    agent = build_agent(session, sdk=SimpleNamespace(Agent=FakeAgent, Field=lambda **kw: kw), handoff=gate)
    call = FakeCall()
    agent.handlers['start'](call)
    return session, agent, call, gate


def test_human_before_load_disabled_is_honest_and_does_not_save():
    session, agent, call, gate = handoff_setup()
    load_field = next(f for f in call.task['checklist'] if f['key'].endswith('_load'))
    assert load_field['required'] is False
    complete(agent, call, action='human')
    assert gate.calls == [call.id]
    assert call.get_variable('dock_load') is None
    assert call.task_id.startswith('identify_')
    assert session.reports == []
    assert any('not enabled' in text for text in call.instructions)


@pytest.mark.parametrize('phase', ['report', 'confirm'])
def test_human_interrupts_report_without_persistence(phase):
    session, agent, call, gate = handoff_setup('requested')
    complete(agent, call, load='LL-88421')
    complete(agent, call, action='report')
    if phase == 'confirm':
        complete(agent, call, state='unloading_started', time='now', detail='actually started')
        assert call.get_variable('dock_pending')
        completed = complete(agent, call, confirmation='human')
    else:
        completed = complete(agent, call, state='human')
    assert call.get_variable('dock_pending') is None
    assert call.get_variable('dock_task') == 'handoff_pending'
    assert gate.calls == [call.id]
    assert session.reports == []
    agent.handlers['complete'](call, completed)
    assert gate.calls == [call.id]
    assert session.reports == []


@pytest.mark.parametrize('status', ['unavailable', 'cooldown', 'failed'])
def test_unavailable_handoff_resumes_assistance_without_promises(status):
    session, agent, call, gate = handoff_setup(status)
    complete(agent, call, load='LL-88421')
    complete(agent, call, action='human')
    assert call.task_id.startswith('offer_')
    assert session.reports == []
    assert any('no callback is promised' in text for text in call.instructions)


def test_gate_duplicate_does_not_request_again_or_claim_connected():
    session, agent, call, gate = handoff_setup('duplicate')
    original = complete(agent, call, action='human')
    agent.handlers['complete'](call, original)
    assert gate.calls == [call.id]
    assert call.get_variable('dock_task') == 'handoff_pending'
    assert any('Do not claim a person answered' in text for text in call.instructions)
    assert session.reports == []


def test_anger_without_explicit_human_choice_does_not_request_handoff():
    session, agent, call, gate = handoff_setup()
    complete(agent, call, load='LL-88421')
    agent.handlers['question'](call, 'This is ridiculous, where is my load?')
    assert gate.calls == []
    assert session.reports == []


def test_gate_storage_failure_is_unavailable_and_drops_pending():
    session, agent, call, gate = handoff_setup()
    begin_report(agent, call)
    def fail(call):
        raise OSError('private storage path')
    gate.request = fail
    complete(agent, call, confirmation='human')
    assert call.get_variable('dock_pending') is None
    assert call.task_id.startswith('offer_')
    assert ('Human handoff result', {'status': 'unavailable'}) in call.infos
    assert session.reports == []
