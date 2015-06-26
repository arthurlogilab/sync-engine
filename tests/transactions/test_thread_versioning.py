from tests.util.base import add_fake_message
# STOPSHIP(emfree) need to also meaningfully test that message attribute and
# category mutations increment thread version and create thread delta

def test_adding_and_removing_message_on_thread_increments_version(
        db, thread, default_namespace):
    assert thread.version == 0
    message = add_fake_message(db.session, default_namespace.id, thread)
    thread.messages.remove(message)
    db.session.commit()
    assert thread.version == 2
