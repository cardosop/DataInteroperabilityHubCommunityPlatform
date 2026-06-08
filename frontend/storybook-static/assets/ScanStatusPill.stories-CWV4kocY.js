import{j as N}from"./jsx-runtime-u17CrQMm.js";const n={PENDING_SCAN:"PENDING_SCAN",CLEAN:"CLEAN",INFECTED:"INFECTED",SCAN_UNAVAILABLE:"SCAN_UNAVAILABLE",SCAN_ERROR:"SCAN_ERROR"},A="_pill_t9brx_1",E="_pillPending_t9brx_12",m="_pillClean_t9brx_18",_="_pillInfected_t9brx_24",C="_pillUnavailable_t9brx_30",g="_pillError_t9brx_36",I="_pillUnknown_t9brx_42",a={pill:A,pillPending:E,pillClean:m,pillInfected:_,pillUnavailable:C,pillError:g,pillUnknown:I},L={PENDING_SCAN:"Pending scan",CLEAN:"Clean",INFECTED:"Infected",SCAN_UNAVAILABLE:"Scan unavailable",SCAN_ERROR:"Scan error"};function f(e){switch(e){case"PENDING_SCAN":return a.pillPending;case"CLEAN":return a.pillClean;case"INFECTED":return a.pillInfected;case"SCAN_UNAVAILABLE":return a.pillUnavailable;case"SCAN_ERROR":return a.pillError;default:return a.pillUnknown}}function u({status:e,scannedAt:i,testId:d="scan-status-pill"}){const o=L[e]??e,p=i!=null&&i!==""?`Last scan: ${new Date(i).toLocaleString()}`:void 0,S=p?`${o}. ${p}`:`${o}. Malware scan status.`;return N.jsx("span",{className:`${a.pill} ${f(e)}`,"data-testid":d,"data-scan-status":e,title:p,role:"status","aria-label":S,children:o})}u.__docgenInfo={description:"",methods:[],displayName:"ScanStatusPill",props:{status:{required:!0,tsType:{name:"union",raw:"FileScanStatus | string",elements:[{name:"FileScanStatus"},{name:"string"}]},description:""},scannedAt:{required:!1,tsType:{name:"union",raw:"string | null",elements:[{name:"string"},{name:"null"}]},description:""},testId:{required:!1,tsType:{name:"string"},description:"Unique id for tables with multiple rows (defaults to `scan-status-pill`).",defaultValue:{value:"'scan-status-pill'",computed:!1}}}};const b={title:"Features/Files/ScanStatusPill",component:u,tags:["autodocs"],parameters:{docs:{description:{component:"Chromatic captures one snapshot per story — five variants = Gap 7 / D260.7 coverage."}}}},s={args:{status:n.PENDING_SCAN}},t={args:{status:n.CLEAN,scannedAt:"2025-01-15T10:30:00.000Z"}},r={args:{status:n.INFECTED,scannedAt:"2025-01-15T10:31:00.000Z"}},l={args:{status:n.SCAN_UNAVAILABLE}},c={args:{status:n.SCAN_ERROR,scannedAt:"2025-01-15T10:32:00.000Z"}};s.parameters={...s.parameters,docs:{...s.parameters?.docs,source:{originalSource:`{
  args: {
    status: FileScanStatus.PENDING_SCAN
  }
}`,...s.parameters?.docs?.source}}};t.parameters={...t.parameters,docs:{...t.parameters?.docs,source:{originalSource:`{
  args: {
    status: FileScanStatus.CLEAN,
    scannedAt: '2025-01-15T10:30:00.000Z'
  }
}`,...t.parameters?.docs?.source}}};r.parameters={...r.parameters,docs:{...r.parameters?.docs,source:{originalSource:`{
  args: {
    status: FileScanStatus.INFECTED,
    scannedAt: '2025-01-15T10:31:00.000Z'
  }
}`,...r.parameters?.docs?.source}}};l.parameters={...l.parameters,docs:{...l.parameters?.docs,source:{originalSource:`{
  args: {
    status: FileScanStatus.SCAN_UNAVAILABLE
  }
}`,...l.parameters?.docs?.source}}};c.parameters={...c.parameters,docs:{...c.parameters?.docs,source:{originalSource:`{
  args: {
    status: FileScanStatus.SCAN_ERROR,
    scannedAt: '2025-01-15T10:32:00.000Z'
  }
}`,...c.parameters?.docs?.source}}};const U=["PendingScan","Clean","Infected","ScanUnavailable","ScanError"];export{t as Clean,r as Infected,s as PendingScan,c as ScanError,l as ScanUnavailable,U as __namedExportsOrder,b as default};
