import{j as e}from"./jsx-runtime-u17CrQMm.js";const L=new Set(["FIELD_ADDED"]),y=new Set(["FIELD_REMOVED"]),b=new Set(["FIELD_TYPE_CHANGED","FIELD_NULLABLE_CHANGED","FIELD_PROPERTY_CHANGED","PRIMARY_KEY_CHANGED","UNIQUE_CONSTRAINT_CHANGED","INDEX_RECOMMENDATION_CHANGED"]);function t(r){return L.has(r)?"added":y.has(r)?"removed":b.has(r)?"modified":"other"}function h(r){if(r==null)return"—";if(typeof r=="object")try{return JSON.stringify(r)}catch{return String(r)}return String(r)}function p({compatibilityLevel:r,summary:f,changes:n,version1Label:u,version2Label:g}){const E=n.filter(i=>t(i.type)==="added"),D=n.filter(i=>t(i.type)==="removed"),_=n.filter(i=>t(i.type)==="modified"),c=n.filter(i=>t(i.type)==="other"),m=Object.entries(f).filter(([,i])=>i>0);function a(i){return i.length===0?e.jsx("p",{className:"dataset-version-diff-empty",children:"No changes in this category."}):e.jsx("div",{className:"dataset-version-diff-table-wrap",children:e.jsxs("table",{className:"dataset-version-diff-table",children:[e.jsx("thead",{children:e.jsxs("tr",{children:[e.jsx("th",{scope:"col",children:"Field"}),e.jsx("th",{scope:"col",children:"Change"}),e.jsx("th",{scope:"col",children:"Previous"}),e.jsx("th",{scope:"col",children:"New"}),e.jsx("th",{scope:"col",children:"Breaking"})]})}),e.jsx("tbody",{children:i.map((s,v)=>e.jsxs("tr",{children:[e.jsx("td",{children:s.field_name??"—"}),e.jsx("td",{children:s.description||s.type}),e.jsx("td",{children:h(s.old_value)}),e.jsx("td",{children:h(s.new_value)}),e.jsx("td",{children:s.breaking?e.jsx("span",{className:"dataset-version-diff-breaking",children:"Yes"}):"No"})]},`${s.type}-${s.field_name??"schema"}-${v}`))})]})})}return e.jsxs("section",{className:"dataset-version-diff-view","data-testid":"dataset-version-diff-view","aria-label":"Schema comparison",children:[e.jsx("div",{className:"dataset-version-diff-meta",children:e.jsxs("dl",{children:[e.jsx("dt",{children:"Compared"}),e.jsxs("dd",{children:[u," → ",g]}),e.jsx("dt",{children:"Compatibility"}),e.jsx("dd",{children:r}),e.jsx("dt",{children:"Total changes"}),e.jsx("dd",{children:n.length})]})}),m.length>0?e.jsxs("div",{"data-testid":"dataset-version-diff-summary",children:[e.jsx("strong",{children:"Summary"}),e.jsx("ul",{children:m.map(([i,s])=>e.jsxs("li",{children:[i,": ",s]},i))})]}):null,e.jsxs("div",{className:"dataset-version-diff-section",role:"region","aria-label":"Added fields",children:[e.jsx("h4",{children:"Added fields"}),a(E)]}),e.jsxs("div",{className:"dataset-version-diff-section",role:"region","aria-label":"Removed fields",children:[e.jsx("h4",{children:"Removed fields"}),a(D)]}),e.jsxs("div",{className:"dataset-version-diff-section",role:"region","aria-label":"Modified fields",children:[e.jsx("h4",{children:"Modified fields"}),a(_)]}),c.length>0?e.jsxs("div",{className:"dataset-version-diff-section",role:"region","aria-label":"Other schema changes",children:[e.jsx("h4",{children:"Other schema changes"}),a(c)]}):null]})}p.__docgenInfo={description:"",methods:[],displayName:"DatasetVersionDiffView",props:{compatibilityLevel:{required:!0,tsType:{name:"string"},description:""},summary:{required:!0,tsType:{name:"Record",elements:[{name:"string"},{name:"number"}],raw:"Record<string, number>"},description:""},changes:{required:!0,tsType:{name:"Array",elements:[{name:"DatasetSchemaEvolutionChange"}],raw:"DatasetSchemaEvolutionChange[]"},description:""},version1Label:{required:!0,tsType:{name:"string"},description:""},version2Label:{required:!0,tsType:{name:"string"},description:""}}};const x={title:"Features/Datasets/DatasetVersionDiffView",component:p,tags:["autodocs"],parameters:{docs:{description:{component:"Chromatic captures snapshots per story (Gap 5 / Phase 260.3.A)."}}}},d={args:{compatibilityLevel:"BACKWARD_COMPATIBLE",summary:{FIELD_ADDED:1,FIELD_REMOVED:0},changes:[{type:"FIELD_ADDED",field_name:"region",description:"Field 'region' added",breaking:!1,old_value:null,new_value:{name:"region",data_type:"string",nullable:!0}}],version1Label:"Version 1 (1.0.0)",version2Label:"Version 2 (1.1.0)"}},o={args:{compatibilityLevel:"INCOMPATIBLE",summary:{FIELD_TYPE_CHANGED:1},changes:[{type:"FIELD_TYPE_CHANGED",field_name:"id",description:"Field 'id' type changed from string to integer",breaking:!0,old_value:"string",new_value:"integer"}],version1Label:"Version 1",version2Label:"Version 2"}},l={args:{compatibilityLevel:"FULLY_COMPATIBLE",summary:{},changes:[],version1Label:"Version 3",version2Label:"Version 3"}};d.parameters={...d.parameters,docs:{...d.parameters?.docs,source:{originalSource:`{
  args: {
    compatibilityLevel: 'BACKWARD_COMPATIBLE',
    summary: {
      FIELD_ADDED: 1,
      FIELD_REMOVED: 0
    },
    changes: [{
      type: 'FIELD_ADDED',
      field_name: 'region',
      description: "Field 'region' added",
      breaking: false,
      old_value: null,
      new_value: {
        name: 'region',
        data_type: 'string',
        nullable: true
      }
    }],
    version1Label: 'Version 1 (1.0.0)',
    version2Label: 'Version 2 (1.1.0)'
  }
}`,...d.parameters?.docs?.source}}};o.parameters={...o.parameters,docs:{...o.parameters?.docs,source:{originalSource:`{
  args: {
    compatibilityLevel: 'INCOMPATIBLE',
    summary: {
      FIELD_TYPE_CHANGED: 1
    },
    changes: [{
      type: 'FIELD_TYPE_CHANGED',
      field_name: 'id',
      description: "Field 'id' type changed from string to integer",
      breaking: true,
      old_value: 'string',
      new_value: 'integer'
    }],
    version1Label: 'Version 1',
    version2Label: 'Version 2'
  }
}`,...o.parameters?.docs?.source}}};l.parameters={...l.parameters,docs:{...l.parameters?.docs,source:{originalSource:`{
  args: {
    compatibilityLevel: 'FULLY_COMPATIBLE',
    summary: {},
    changes: [],
    version1Label: 'Version 3',
    version2Label: 'Version 3'
  }
}`,...l.parameters?.docs?.source}}};const A=["BackwardCompatible","BreakingTypeChange","EmptyDiff"];export{d as BackwardCompatible,o as BreakingTypeChange,l as EmptyDiff,A as __namedExportsOrder,x as default};
