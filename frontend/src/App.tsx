import { useEffect, useState } from "react";
import { Activity, CircleDollarSign, Database, FileCheck2, FileSearch, Gauge, HeartPulse, Menu, UploadCloud } from "lucide-react";
import { Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";
import type { Claim, Event, Metrics, Run, RunDetail } from "./types";

const EXPECTED = ["claim_id","patient_id","provider_id","diagnosis_code","procedure_code","claim_amount","claim_date","claim_status"];
const money = new Intl.NumberFormat("en-US", {style:"currency", currency:"USD"});
const date = (value: string) => new Date(value).toLocaleString();
const title = (value: string) => value.replaceAll("_", " ");

function Status({value}:{value:string}) {
  return <span className={`status ${value}`}>{title(value)}</span>;
}

function Layout() {
  const [open, setOpen] = useState(false);
  const links = [
    ["/", Gauge, "Dashboard"], ["/upload", UploadCloud, "Upload CSV"], ["/runs", Activity, "Pipeline Runs"],
    ["/claims", Database, "Claims"], ["/schema-events", FileSearch, "Schema Drift"],
  ] as const;
  return <div className="app">
    <aside className={open ? "open" : ""}>
      <div className="brand"><span><HeartPulse size={22}/></span><div>ClaimHeal<small>ETL OPERATIONS</small></div></div>
      <nav>{links.map(([to,Icon,label]) => <NavLink key={to} to={to} end={to === "/"} onClick={()=>setOpen(false)}><Icon size={18}/>{label}</NavLink>)}</nav>
      <div className="side-foot"><i></i><div>Pipeline healthy<small>PostgreSQL connected</small></div></div>
    </aside>
    <main><header><button className="menu" onClick={()=>setOpen(!open)}><Menu/></button><div><b>Healthcare Claims</b><span>Self-Healing Data Platform</span></div><div className="environment">● LOCAL ENV</div></header><div className="content"><Routes>
      <Route path="/" element={<Dashboard/>}/><Route path="/upload" element={<Upload/>}/><Route path="/runs" element={<Runs/>}/>
      <Route path="/runs/:id" element={<RunView/>}/><Route path="/claims" element={<Claims/>}/><Route path="/schema-events" element={<Events/>}/>
    </Routes></div></main>
  </div>
}

function Page({eyebrow, heading, children, action}:{eyebrow:string;heading:string;children:React.ReactNode;action?:React.ReactNode}) {
  return <><div className="page-head"><div><p>{eyebrow}</p><h1>{heading}</h1></div>{action}</div>{children}</>;
}

function Loading(){ return <div className="loading">Loading pipeline data…</div> }
function ErrorBox({message}:{message:string}){ return <div className="error">{message}</div> }

function Dashboard() {
  const [data,setData]=useState<Metrics|null>(null); const [error,setError]=useState("");
  useEffect(()=>{api.metrics().then(setData).catch(e=>setError(e.message))},[]);
  if(error) return <ErrorBox message={error}/>; if(!data) return <Loading/>;
  const cards = [
    ["Claims loaded",data.total_claims,Database,"teal"],["Acceptance rate",`${data.acceptance_rate}%`,FileCheck2,"blue"],
    ["Claim value",money.format(data.total_claim_amount),CircleDollarSign,"gold"],["Schema events",data.schema_events,FileSearch,"purple"],
  ] as const;
  return <Page eyebrow="OPERATIONS OVERVIEW" heading="Claims pipeline command center" action={<Link className="button" to="/upload"><UploadCloud size={17}/>Upload claims</Link>}>
    <section className="metrics">{cards.map(([label,value,Icon,color])=><article className="metric" key={label}><div className={`metric-icon ${color}`}><Icon/></div><span>{label}</span><strong>{value}</strong><small>Across {data.total_runs} pipeline runs</small></article>)}</section>
    <div className="grid-two"><section className="panel"><div className="panel-head"><div><p>RECENT ACTIVITY</p><h2>Pipeline runs</h2></div><Link to="/runs">View all →</Link></div><RunTable runs={data.recent_runs}/></section>
    <section className="panel"><div className="panel-head"><div><p>CLAIM DISTRIBUTION</p><h2>Status mix</h2></div></div>
      <div className="distribution">{Object.entries(data.status_breakdown).length ? Object.entries(data.status_breakdown).map(([status,count])=><div key={status}><span><i className={status}></i>{title(status)}</span><b>{count}</b><em style={{width:`${count/data.total_claims*100}%`}}/></div>) : <div className="empty">Upload a claims CSV to populate this chart.</div>}</div>
    </section></div>
  </Page>
}

function RunTable({runs}:{runs:Run[]}) {
  return <div className="table-wrap"><table><thead><tr><th>File</th><th>Status</th><th>Records</th><th>Accepted</th><th>Rejected</th><th>Created</th></tr></thead><tbody>
    {runs.map(run=><tr key={run.id}><td><Link to={`/runs/${run.id}`} className="file-link">{run.filename}</Link></td><td><Status value={run.status}/></td><td>{run.total_records}</td><td className="good">{run.accepted_records}</td><td className="bad">{run.rejected_records}</td><td>{date(run.created_at)}</td></tr>)}
    {!runs.length&&<tr><td colSpan={6} className="empty">No pipeline runs yet.</td></tr>}
  </tbody></table></div>
}

function Upload() {
  const [file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""); const nav=useNavigate();
  const submit=async()=>{if(!file)return;setBusy(true);setError("");try{const result=await api.upload(file);nav(`/runs/${result.run.id}`)}catch(e){setError((e as Error).message);setBusy(false)}};
  return <Page eyebrow="INGESTION" heading="Upload healthcare claims">
    <div className="upload-grid"><section className="panel upload-panel"><div className="step">01</div><h2>Select source file</h2><p>Upload a UTF-8 CSV. We'll fingerprint its schema and propose repairs before any drifted data is loaded.</p>
      <label className={`dropzone ${file?"selected":""}`}><UploadCloud size={38}/><strong>{file?file.name:"Drop your CSV here"}</strong><span>{file?`${(file.size/1024).toFixed(1)} KB`:"or click to browse · max 10 MB"}</span><input type="file" accept=".csv,text/csv" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
      {error&&<ErrorBox message={error}/>}<button className="button wide" disabled={!file||busy} onClick={submit}>{busy?"Analyzing schema…":"Analyze & upload"}<span>→</span></button>
    </section><section className="panel schema-card"><p>CANONICAL CONTRACT</p><h2>Expected claim schema</h2><div className="schema-list">{EXPECTED.map((field,i)=><div key={field}><code>{field}</code><span>{i===5?"decimal":i===6?"date":"string"}</span></div>)}</div><div className="callout"><HeartPulse size={20}/><div><b>Self-healing is on</b><span>Known aliases are mapped locally. Add an OpenAI key for semantic suggestions on unfamiliar columns.</span></div></div></section></div>
  </Page>
}

function Runs(){const [runs,setRuns]=useState<Run[]|null>(null);useEffect(()=>{api.runs().then(setRuns)},[]);return <Page eyebrow="AUDIT TRAIL" heading="Pipeline runs" action={<Link className="button" to="/upload">New upload</Link>}><section className="panel">{runs?<RunTable runs={runs}/>:<Loading/>}</section></Page>}

function RunView(){
  const {id=""}=useParams();const [run,setRun]=useState<RunDetail|null>(null),[mapping,setMapping]=useState<Record<string,string>>({}),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{api.run(id).then(r=>{setRun(r);setMapping(r.suggested_mapping)}).catch(e=>setError(e.message))},[id]);
  const approve=async()=>{setBusy(true);setError("");try{setRun(await api.approve(id,mapping))}catch(e){setError((e as Error).message)}finally{setBusy(false)}};
  if(error&&!run)return <ErrorBox message={error}/>;if(!run)return <Loading/>;
  return <Page eyebrow="RUN DETAILS" heading={run.filename} action={<Status value={run.status}/>}>
    <div className="run-stats"><div><span>Total rows</span><b>{run.total_records}</b></div><div><span>Accepted</span><b className="good">{run.accepted_records}</b></div><div><span>Rejected</span><b className="bad">{run.rejected_records}</b></div><div><span>Mapping engine</span><b>{title(run.mapping_source||"n/a")}</b></div></div>
    {run.status==="awaiting_approval"&&<section className="panel approval"><div className="panel-head"><div><p>HUMAN-IN-THE-LOOP</p><h2>Review suggested mapping</h2></div><span className="ai-tag">✦ {run.mapping_source}</span></div>
      <p className="muted">Confirm how source columns map to the canonical claims contract. Every required target must be selected exactly once.</p>
      <div className="mapping-grid">{run.detected_columns.map(source=><div key={source}><code>{source}</code><span>→</span><select value={mapping[source]||""} onChange={e=>setMapping(m=>({...m,[source]:e.target.value}))}><option value="">Ignore column</option>{EXPECTED.map(target=><option key={target} value={target}>{target}</option>)}</select></div>)}</div>
      {error&&<ErrorBox message={error}/>}<button className="button" onClick={approve} disabled={busy}>{busy?"Validating & loading…":"Approve mapping and run pipeline"}</button>
    </section>}
    <section className="panel"><div className="panel-head"><div><p>DRIFT OBSERVATIONS</p><h2>Schema events</h2></div></div><EventTable events={run.events}/></section>
  </Page>
}

function Claims(){
  const [claims,setClaims]=useState<Claim[]|null>(null),[search,setSearch]=useState("");useEffect(()=>{const t=setTimeout(()=>api.claims(search).then(r=>setClaims(r.items)),250);return()=>clearTimeout(t)},[search]);
  return <Page eyebrow="CURATED DATA" heading="Accepted claims" action={<input className="search" placeholder="Search claim ID…" value={search} onChange={e=>setSearch(e.target.value)}/>}>
    <section className="panel"><div className="table-wrap"><table><thead><tr><th>Claim ID</th><th>Patient</th><th>Provider</th><th>Diagnosis</th><th>Procedure</th><th>Amount</th><th>Service date</th><th>Status</th></tr></thead><tbody>{claims?.map(c=><tr key={c.id}><td><b>{c.claim_id}</b></td><td>{c.patient_id}</td><td>{c.provider_id}</td><td><code>{c.diagnosis_code}</code></td><td><code>{c.procedure_code}</code></td><td>{money.format(Number(c.claim_amount))}</td><td>{c.claim_date}</td><td><Status value={c.claim_status}/></td></tr>)}{claims&&!claims.length&&<tr><td colSpan={8} className="empty">No accepted claims found.</td></tr>}</tbody></table></div>{!claims&&<Loading/>}</section>
  </Page>
}

function EventTable({events}:{events:Event[]}){return <div className="table-wrap"><table><thead><tr><th>Source column</th><th>Mapped target</th><th>Type</th><th>Confidence</th><th>Resolution</th></tr></thead><tbody>{events.map(e=><tr key={e.id}><td><code>{e.source_column}</code></td><td><code>{e.target_column||"—"}</code></td><td>{title(e.event_type)}</td><td>{e.confidence?`${Math.round(e.confidence*100)}%`:"—"}</td><td><Status value={e.resolution}/></td></tr>)}{!events.length&&<tr><td colSpan={5} className="empty">No schema drift detected.</td></tr>}</tbody></table></div>}
function Events(){const [events,setEvents]=useState<Event[]|null>(null);useEffect(()=>{api.events().then(setEvents)},[]);return <Page eyebrow="SCHEMA INTELLIGENCE" heading="Drift event registry"><section className="panel">{events?<EventTable events={events}/>:<Loading/>}</section></Page>}

export default Layout;
