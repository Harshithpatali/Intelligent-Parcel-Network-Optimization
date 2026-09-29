import json,logging,sys,time
from uuid import uuid4
from contextvars import ContextVar
request_id_ctx:ContextVar[str]=ContextVar('request_id',default='-')
class JsonFormatter(logging.Formatter):
    def format(self,record):
        p={'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'level':record.levelname,'logger':record.name,'message':record.getMessage(),'request_id':request_id_ctx.get()}
        if record.exc_info:p['exception']=self.formatException(record.exc_info)
        return json.dumps(p,separators=(',',':'))
def configure_logging(level='INFO'):
    h=logging.StreamHandler(sys.stdout); h.setFormatter(JsonFormatter()); root=logging.getLogger(); root.handlers.clear(); root.addHandler(h); root.setLevel(level.upper())
def new_request_id(): return str(uuid4())
