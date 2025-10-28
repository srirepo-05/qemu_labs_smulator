import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

SQLALCHEMY_DATABASE_URL = "sqlite:///./nodes.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class NodeStatus(str, enum.Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(Enum(NodeStatus), default=NodeStatus.STOPPED)
    overlay_path = Column(String, unique=True)
    qemu_pid = Column(Integer, nullable=True)
    vnc_port = Column(Integer, nullable=True)
    guac_connection_id = Column(String, nullable=True)

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()