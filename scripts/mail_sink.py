"""Local-only SMTP inbox for demos. Messages are saved as .eml files, never sent externally."""
import socketserver
from pathlib import Path
from uuid import uuid4
from datetime import datetime

OUTBOX=Path(__file__).resolve().parent.parent/'instance'/'mail'
OUTBOX.mkdir(parents=True,exist_ok=True)

class SMTPHandler(socketserver.StreamRequestHandler):
    def reply(self,line): self.wfile.write((line+'\r\n').encode())
    def handle(self):
        self.reply('220 localhost EMP demo inbox')
        while True:
            line=self.rfile.readline(65536)
            if not line: break
            command=line.decode(errors='replace').strip().upper()
            if command.startswith(('EHLO','HELO')):
                self.reply('250 localhost')
            elif command.startswith(('MAIL FROM:','RCPT TO:','RSET','NOOP')):
                self.reply('250 OK')
            elif command=='DATA':
                self.reply('354 End with a dot')
                chunks=[]
                while True:
                    part=self.rfile.readline(65536)
                    if not part or part in (b'.\r\n',b'.\n'): break
                    chunks.append(part[1:] if part.startswith(b'..') else part)
                target=OUTBOX/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]+'.eml')
                target.write_bytes(b''.join(chunks))
                self.reply('250 Message saved')
            elif command=='QUIT':
                self.reply('221 Bye'); break
            else: self.reply('502 Unsupported command')

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True

if __name__=='__main__':
    print('Local demo email inbox: '+str(OUTBOX),flush=True)
    with Server(('127.0.0.1',1025),SMTPHandler) as server: server.serve_forever()
