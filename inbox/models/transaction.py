from sqlalchemy import (Column, Integer, String, ForeignKey, Index, Enum,
                        inspect)
from sqlalchemy.orm import relationship

from inbox.models.base import MailSyncBase
from inbox.models.mixins import HasPublicID, HasRevisions
from inbox.models.namespace import Namespace


class Transaction(MailSyncBase, HasPublicID):
    """ Transactional log to enable client syncing. """
    # Do delete transactions if their associated namespace is deleted.
    namespace_id = Column(Integer,
                          ForeignKey(Namespace.id, ondelete='CASCADE'),
                          nullable=False)
    namespace = relationship(Namespace)

    object_type = Column(String(20), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    object_public_id = Column(String(191), nullable=False, index=True)
    command = Column(Enum('insert', 'update', 'delete'), nullable=False)

Index('namespace_id_deleted_at', Transaction.namespace_id,
      Transaction.deleted_at)
Index('object_type_record_id', Transaction.object_type, Transaction.record_id)
Index('namespace_id_created_at', Transaction.namespace_id,
      Transaction.created_at)


def create_revisions(session):
    for obj in session.new:
        create_revision(obj, session, 'insert')
    for obj in session.dirty:
        create_revision(obj, session, 'update')
    for obj in session.deleted:
        create_revision(obj, session, 'delete')


def create_revision(obj, session, revision_type):
    assert revision_type in ('insert', 'update', 'delete')
    if (not isinstance(obj, HasRevisions) or
            obj.should_suppress_transaction_creation):
        return
    if revision_type == 'update' and not obj.has_versioned_changes():
        return
    revision = Transaction(command=revision_type, record_id=obj.id,
                           object_type=obj.API_OBJECT_NAME,
                           object_public_id=obj.public_id,
                           namespace_id=obj.namespace.id)
    session.add(revision)


def propagate_changes(session):
    # TODO[k]:
    # 1/ How should many changes to a thread's messages be propagated -
    # i.e. should it result in incrementing thread.version by ONE or MANY?
    # 2/ Combine propagate_changes()/ increment_versions()?
    # 3/ Should this manipulate thread.version directly?
    from inbox.models.message import Message

    for obj in session.dirty:
        if isinstance(obj, Message):
            obj_state = inspect(obj)
            for attr in obj.propagated_attributes:
                if getattr(obj_state.attrs, attr).history.has_changes():
                    obj.thread.changed = obj.thread.changed + 1


def increment_versions(session):
    from inbox.models.thread import Thread
    for obj in session.dirty:
        if isinstance(obj, Thread) and obj.has_versioned_changes():
            # This issues SQL for an atomic increment.
            obj.version = Thread.version + 1
