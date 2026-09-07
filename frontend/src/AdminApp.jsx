import { useEffect, useState } from "react";
import { BellRing, Bot, CheckCircle2, LogOut, Mail, Play, Plus, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "./api";
import "./email-admin.css";

export default function AdminApp() {
  const [password, setPassword] = useState(() => sessionStorage.getItem("futurem_admin_password") || "");
  const [draftPassword, setDraftPassword] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [status, setStatus] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [form, setForm] = useState({ name: "", chat_id: "", email: "", telegram_enabled: true, email_enabled: true });
  const [recentChats, setRecentChats] = useState([]);
  const [busy, setBusy] = useState(false);
  const [scanBusy, setScanBusy] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = async (secret = password) => {
    if (!secret) return;
    setBusy(true); setError("");
    try {
      const [nextStatus, recipientData] = await Promise.all([api.adminStatus(secret), api.adminRecipients(secret)]);
      setStatus(nextStatus); setRecipients(recipientData.items || []); setAuthenticated(true);
      sessionStorage.setItem("futurem_admin_password", secret); setPassword(secret);
    } catch (err) {
      setAuthenticated(false); sessionStorage.removeItem("futurem_admin_password"); setError(err.message);
    } finally { setBusy(false); }
  };

  useEffect(() => { if (password) load(password); }, []);

  const act = async (operation, successText) => {
    setBusy(true); setError(""); setMessage("");
    try { await operation(); await load(); setMessage(successText); }
    catch (err) { setError(err.message); setBusy(false); }
  };

  if (!authenticated) return (
    <main className="admin-login-shell">
      <section className="admin-login-card">
        <div className="admin-mark"><ShieldCheck size={28} /></div>
        <p className="admin-eyebrow">FUTURE:M RADAR</p>
        <h1>Alert Control Center</h1>
        <p>중요 공시 Telegram·이메일 자동 알림 관리자 전용 화면</p>
        <form onSubmit={(event) => { event.preventDefault(); load(draftPassword); }}>
          <label>관리자 비밀번호</label>
          <input type="password" value={draftPassword} onChange={(event) => setDraftPassword(event.target.value)} autoFocus placeholder="ADMIN_PASSWORD" />
          <button disabled={busy || !draftPassword}>{busy ? "확인 중..." : "관리자 로그인"}</button>
        </form>
        {error && <div className="admin-error">{error}</div>}
        <a href="/">← 대시보드로 돌아가기</a>
      </section>
    </main>
  );

  const activeCount = recipients.filter((item) => item.enabled).length;
  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div><p className="admin-eyebrow">SECURE OPERATIONS</p><h1>Multi-Channel Alert Control</h1><p>중요 공시 Telegram·이메일 수신자와 발송 상태를 관리합니다.</p></div>
        <div className="admin-header-actions"><a href="/">대시보드</a><button className="ghost" onClick={() => { sessionStorage.removeItem("futurem_admin_password"); location.reload(); }}><LogOut size={16}/> 로그아웃</button></div>
      </header>

      <section className="admin-stats">
        <article><Bot/><span>Telegram Bot</span><strong>{status?.telegram?.connected ? "CONNECTED" : "CHECK REQUIRED"}</strong><small>{status?.telegram?.username ? `@${status.telegram.username}` : "Bot Token 확인"}</small></article>
        <article><Mail/><span>Email SMTP</span><strong>{status?.email?.configured ? "CONFIGURED" : "CHECK REQUIRED"}</strong><small>{status?.email?.configured ? `${status.email.from_email} · ${status.email.security}` : ".env SMTP 설정 필요"}</small></article>
        <article><BellRing/><span>활성 수신자</span><strong>{activeCount}명</strong><small>전체 등록 {recipients.length}명</small></article>
        <article><RefreshCw/><span>자동 점검 주기</span><strong>{Math.round((status?.poll_seconds || 300) / 60)}분</strong><small>오늘 접수된 주요 공시</small></article>
      </section>

      {(message || error) && <div className={error ? "admin-error admin-banner" : "admin-success admin-banner"}>{error || message}</div>}

      <div className="admin-grid">
        <section className="admin-panel">
          <div className="admin-panel-title"><div><p className="admin-eyebrow">RECIPIENT MANAGEMENT</p><h2>알림 수신자</h2></div><button className="ghost" disabled={busy} onClick={() => load()}><RefreshCw size={15}/> 새로고침</button></div>
          <div className="recipient-list">
            {recipients.length === 0 && <div className="admin-empty">등록된 수신자가 없습니다.</div>}
            {recipients.map((recipient) => (
              <article className="recipient-row" key={recipient.id}>
                <div className={`recipient-status ${recipient.enabled ? "on" : "off"}`}><CheckCircle2 size={18}/></div>
                <div className="recipient-main"><strong>{recipient.name}</strong>{recipient.chat_id && <span>Telegram · {recipient.chat_id}</span>}{recipient.email && <span>Email · {recipient.email}</span>}<small>{recipient.enabled ? "중요 공시 자동 수신 중" : "전체 수신 중지됨"}</small><div className="channel-toggles">{recipient.chat_id && <button className={recipient.telegram_enabled ? "on" : ""} onClick={() => act(() => api.updateRecipient(password, recipient.id, {telegram_enabled:!recipient.telegram_enabled}), "Telegram 수신 설정을 변경했습니다.")}>Telegram {recipient.telegram_enabled ? "ON" : "OFF"}</button>}{recipient.email && <button className={recipient.email_enabled ? "on" : ""} onClick={() => act(() => api.updateRecipient(password, recipient.id, {email_enabled:!recipient.email_enabled}), "이메일 수신 설정을 변경했습니다.")}>Email {recipient.email_enabled ? "ON" : "OFF"}</button>}</div></div>
                <div className="recipient-actions">
                  <button disabled={busy} onClick={() => act(() => api.testRecipient(password, recipient.id), `${recipient.name}님에게 테스트 메시지를 발송했습니다.`)}><Play size={14}/> 테스트</button>
                  <button disabled={busy} onClick={() => act(() => api.updateRecipient(password, recipient.id, { enabled: !recipient.enabled }), recipient.enabled ? "수신을 중지했습니다." : "수신을 다시 시작했습니다.")}>{recipient.enabled ? "수신 중지" : "수신 재개"}</button>
                  <button className="danger" disabled={busy} onClick={() => { if (confirm(`${recipient.name} 수신자를 삭제할까요?`)) act(() => api.deleteRecipient(password, recipient.id), "수신자를 삭제했습니다."); }}><Trash2 size={14}/></button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="admin-panel admin-side-panel">
          <p className="admin-eyebrow">ADD RECIPIENT</p><h2>새 수신자 등록</h2>
          <p className="admin-help">Telegram은 봇 대화 시작 후 Chat ID를 등록합니다. 이메일만 등록해도 수신자로 추가할 수 있습니다.</p>
          {status?.telegram?.username && <a className="bot-link" href={`https://t.me/${status.telegram.username}`} target="_blank" rel="noreferrer">@{status.telegram.username} 봇 열기 ↗</a>}
          <button className="discover-button" disabled={busy || !status?.telegram?.connected} onClick={async () => { setBusy(true); setError(""); try { const data = await api.telegramChats(password); setRecentChats(data.items || []); setMessage(`최근 대화 ${data.items?.length || 0}건을 확인했습니다.`); } catch (err) { setError(err.message); } finally { setBusy(false); } }}><RefreshCw size={15}/> 봇 대화 사용자 불러오기</button>
          {recentChats.length > 0 && <div className="recent-chat-list">{recentChats.map((chat) => <button key={chat.chat_id} onClick={() => setForm({...form,name:chat.name,chat_id:chat.chat_id})}><strong>{chat.name}</strong><span>{chat.chat_id}</span></button>)}</div>}
          <form onSubmit={(event) => { event.preventDefault(); act(() => api.addRecipient(password, form), `${form.name} 수신자를 등록했습니다.`); setForm({name:"",chat_id:"",email:"",telegram_enabled:true,email_enabled:true}); }}>
            <label>수신자 이름</label><input value={form.name} onChange={(event) => setForm({...form, name:event.target.value})} placeholder="예: 전략기획 담당자" />
            <label>Telegram Chat ID</label><input value={form.chat_id} onChange={(event) => setForm({...form, chat_id:event.target.value})} placeholder="예: 123456789" />
            <label>이메일 주소</label><input type="email" value={form.email} onChange={(event) => setForm({...form, email:event.target.value})} placeholder="예: strategy@company.com" />
            <div className="new-channel-options"><label><input type="checkbox" checked={form.telegram_enabled} onChange={event=>setForm({...form,telegram_enabled:event.target.checked})}/> Telegram</label><label><input type="checkbox" checked={form.email_enabled} onChange={event=>setForm({...form,email_enabled:event.target.checked})}/> Email</label></div>
            <button disabled={busy || !form.name.trim() || (!form.chat_id.trim() && !form.email.trim())}><Plus size={17}/> 수신자 추가</button>
          </form>
          <div className="admin-divider" />
          <h3>자동 발송 기준</h3>
          <div className="monitor-active"><i /> 자동 감시 활성화 · {Math.round((status?.poll_seconds || 300) / 60)}분 주기</div>
          <ul><li>단일판매·공급계약 체결</li><li>신규 시설투자</li><li>타법인 주식·출자증권 취득</li><li>유상증자 관련 주요 공시</li></ul>
          <button className="scan-button" disabled={busy || scanBusy} onClick={async () => { setScanBusy(true); setScanResult(null); setError(""); try { const result = await api.scanAlerts(password); setScanResult(result); } catch (err) { setError(err.message); } finally { setScanBusy(false); } }}><RefreshCw className={scanBusy ? "spin" : ""} size={15}/>{scanBusy ? "중요 공시 점검 중…" : "지금 중요 공시 점검"}</button>
          {scanResult && <div className="scan-result"><CheckCircle2 size={16}/><div><strong>점검 완료</strong><span>{scanResult.found ? `주요 공시 ${scanResult.found}건 · Telegram ${scanResult.telegram_sent||0}건 · Email ${scanResult.email_sent||0}건` : "오늘 새로 감지된 중요 공시가 없습니다."}</span></div></div>}
        </aside>
      </div>
    </main>
  );
}
