#!/usr/bin/env node
/**
 * Architecture Analysis Script for OntologyEngine
 * Analyzes file structure, imports, and directory patterns to identify logical architecture layers.
 */

const fs = require('fs');
const path = require('path');

// Read input JSON
const inputPath = process.argv[2];
const outputPath = process.argv[3];

if (!inputPath || !outputPath) {
  console.error('Usage: node ua-arch-analyze.js <input.json> <output.json>');
  process.exit(1);
}

let input;
try {
  const data = fs.readFileSync(inputPath, 'utf8');
  input = JSON.parse(data);
} catch (e) {
  console.error('Error reading input file:', e.message);
  process.exit(1);
}

const { fileNodes, importEdges, allEdges } = input;

// ============================================
// A. Directory Grouping
// ============================================
function getDirectoryGroup(filePath) {
  // Remove prefix like "ontology_engine/" or "ontology-engine-ui/src/"
  const parts = filePath.split('/');

  // Group by first meaningful directory segment
  if (parts.length === 1) {
    return 'root';
  }

  // Skip common prefixes
  let startIndex = 0;
  if (parts[0] === 'ontology_engine' || parts[0] === 'ontology-engine-ui') {
    startIndex = 1;
  }

  if (parts.length <= startIndex + 1) {
    // Check for file type patterns
    const filename = parts[parts.length - 1];
    if (filename.startsWith('test_') || filename.endsWith('.test.ts') || filename.endsWith('.spec.ts')) {
      return 'test';
    }
    if (filename.endsWith('.config.') || filename.includes('config')) {
      return 'config';
    }
    return 'root';
  }

  return parts[startIndex];
}

const directoryGroups = {};
const nodeToDirectory = {};

fileNodes.forEach(node => {
  const group = getDirectoryGroup(node.filePath);
  if (!directoryGroups[group]) {
    directoryGroups[group] = [];
  }
  directoryGroups[group].push(node.id);
  nodeToDirectory[node.id] = group;
});

// ============================================
// B. Node Type Grouping
// ============================================
const nodeTypeGroups = {};
fileNodes.forEach(node => {
  const type = node.type;
  if (!nodeTypeGroups[type]) {
    nodeTypeGroups[type] = [];
  }
  nodeTypeGroups[type].push(node.id);
});

// ============================================
// C. Import Adjacency Matrix
// ============================================
const fileFanOut = {};
const fileFanIn = {};
const groupFanOut = {};
const groupFanIn = {};

fileNodes.forEach(node => {
  fileFanOut[node.id] = 0;
  fileFanIn[node.id] = 0;
});

Object.keys(directoryGroups).forEach(group => {
  groupFanOut[group] = new Set();
  groupFanIn[group] = new Set();
});

importEdges.forEach(edge => {
  // Fan out
  if (fileFanOut[edge.source] !== undefined) {
    fileFanOut[edge.source]++;
  }
  // Fan in
  if (fileFanIn[edge.target] !== undefined) {
    fileFanIn[edge.target]++;
  }

  // Group level
  const sourceGroup = nodeToDirectory[edge.source];
  const targetGroup = nodeToDirectory[edge.target];
  if (sourceGroup && targetGroup) {
    groupFanOut[sourceGroup].add(targetGroup);
    groupFanIn[targetGroup].add(sourceGroup);
  }
});

// ============================================
// D. Cross-Category Dependency Analysis
// ============================================
const crossCategoryEdges = {};
allEdges.forEach(edge => {
  const sourceNode = fileNodes.find(n => n.id === edge.source);
  const targetNode = fileNodes.find(n => n.id === edge.target);
  if (!sourceNode || !targetNode) return;

  const key = `${sourceNode.type} -> ${targetNode.type}:${edge.type}`;
  if (!crossCategoryEdges[key]) {
    crossCategoryEdges[key] = { fromType: sourceNode.type, toType: targetNode.type, edgeType: edge.type, count: 0 };
  }
  crossCategoryEdges[key].count++;
});

const crossCategoryEdgesArray = Object.values(crossCategoryEdges);

// ============================================
// E. Inter-Group Import Frequency
// ============================================
const interGroupImports = {};
importEdges.forEach(edge => {
  const sourceGroup = nodeToDirectory[edge.source];
  const targetGroup = nodeToDirectory[edge.target];
  if (!sourceGroup || !targetGroup) return;

  const key = `${sourceGroup} -> ${targetGroup}`;
  if (!interGroupImports[key]) {
    interGroupImports[key] = { from: sourceGroup, to: targetGroup, count: 0 };
  }
  interGroupImports[key].count++;
});

const interGroupImportsArray = Object.values(interGroupImports);

// ============================================
// F. Intra-Group Import Density
// ============================================
const intraGroupDensity = {};
Object.keys(directoryGroups).forEach(group => {
  let internalEdges = 0;
  let totalEdges = 0;

  importEdges.forEach(edge => {
    const sourceGroup = nodeToDirectory[edge.source];
    const targetGroup = nodeToDirectory[edge.target];
    if (sourceGroup === group || targetGroup === group) {
      totalEdges++;
      if (sourceGroup === group && targetGroup === group) {
        internalEdges++;
      }
    }
  });

  intraGroupDensity[group] = {
    internalEdges,
    totalEdges,
    density: totalEdges > 0 ? internalEdges / totalEdges : 0
  };
});

// ============================================
// G. Directory Pattern Matching
// ============================================
const PATTERN_MAP = {
  'routes': 'api',
  'api': 'api',
  'controllers': 'api',
  'endpoints': 'api',
  'handlers': 'api',
  'services': 'service',
  'core': 'service',
  'lib': 'service',
  'domain': 'service',
  'logic': 'service',
  'engine': 'service',
  'categorization': 'service',
  'expression': 'service',
  'metric': 'service',
  'query': 'service',
  'rule': 'service',
  'models': 'data',
  'db': 'data',
  'data': 'data',
  'persistence': 'data',
  'repository': 'data',
  'entities': 'data',
  'storage': 'data',
  'duckdb': 'data',
  'components': 'ui',
  'views': 'ui',
  'pages': 'ui',
  'ui': 'ui',
  'layouts': 'ui',
  'screens': 'ui',
  'middleware': 'middleware',
  'plugins': 'middleware',
  'interceptors': 'middleware',
  'guards': 'middleware',
  'utils': 'utility',
  'helpers': 'utility',
  'common': 'utility',
  'shared': 'utility',
  'tools': 'utility',
  'dto': 'types',
  'types': 'types',
  'interfaces': 'types',
  'schemas': 'types',
  'contracts': 'types',
  '__tests__': 'test',
  'test': 'test',
  'tests': 'test',
  'spec': 'test',
  'specs': 'test',
  'visualization': 'visualization',
  'builders': 'visualization',
  'explainers': 'visualization',
  'simulator': 'visualization',
  'semantic_space': 'data',
  'cli': 'entry',
  'cmd': 'entry',
  'bin': 'entry',
  'instances': 'data',
  'store': 'state',
  'stores': 'state'
};

const patternMatches = {};
Object.keys(directoryGroups).forEach(group => {
  const normalizedGroup = group.toLowerCase();
  patternMatches[group] = PATTERN_MAP[normalizedGroup] || 'service';
});

// ============================================
// H. Deployment Topology Detection
// ============================================
const infraFiles = [];
let hasDockerfile = false;
let hasCompose = false;
let hasK8s = false;
let hasTerraform = false;
let hasCI = false;

fileNodes.forEach(node => {
  const filepath = node.filePath.toLowerCase();
  if (filepath === 'dockerfile' || filepath.endsWith('/dockerfile')) hasDockerfile = true;
  if (filepath.includes('docker-compose')) hasCompose = true;
  if (filepath.includes('kubernetes') || filepath.includes('k8s') || filepath.includes('helm')) hasK8s = true;
  if (filepath.includes('terraform') || filepath.endsWith('.tf') || filepath.endsWith('.tfvars')) hasTerraform = true;
  if (filepath.includes('.github/workflows') || filepath.includes('.gitlab-ci') || filepath.includes('jenkinsfile')) hasCI = true;

  if (node.type === 'service' || node.type === 'resource') {
    infraFiles.push(node.filePath);
  }
});

const deploymentTopology = {
  hasDockerfile,
  hasCompose,
  hasK8s,
  hasTerraform,
  hasCI,
  infraFiles
};

// ============================================
// I. Data Pipeline Detection
// ============================================
const schemaFiles = [];
const migrationFiles = [];
const dataModelFiles = [];
const apiHandlerFiles = [];

fileNodes.forEach(node => {
  const filepath = node.filePath.toLowerCase();
  if (filepath.endsWith('.graphql') || filepath.endsWith('.gql') || filepath.endsWith('.proto') || filepath.includes('schema')) {
    schemaFiles.push(node.filePath);
  }
  if (filepath.includes('migration') || filepath.endsWith('.sql')) {
    migrationFiles.push(node.filePath);
  }
  if (filepath.includes('model') && (filepath.includes('ontology_engine/core') || filepath.includes('ontology_engine/engine'))) {
    dataModelFiles.push(node.filePath);
  }
  if (filepath.includes('routes') && filepath.includes('api')) {
    apiHandlerFiles.push(node.filePath);
  }
});

const dataPipeline = {
  schemaFiles,
  migrationFiles,
  dataModelFiles,
  apiHandlerFiles
};

// ============================================
// J. Documentation Coverage
// ============================================
const docGroups = new Set();
fileNodes.forEach(node => {
  if (node.type === 'document') {
    // Try to determine which group this doc belongs to
    const filepath = node.filePath.toLowerCase();
    if (filepath.includes('discuss')) {
      docGroups.add('discuss');
    } else if (filepath.includes('docs')) {
      // Extract directory from docs/
      const parts = filepath.split('/');
      if (parts.length >= 2) {
        docGroups.add(parts[1]);
      }
    }
  }
});

const totalGroups = Object.keys(directoryGroups).length;
const groupsWithDocs = docGroups.size;
const allGroups = new Set(Object.keys(directoryGroups));
const undocumentedGroups = [...allGroups].filter(g => !docGroups.has(g));

const docCoverage = {
  groupsWithDocs,
  totalGroups,
  coverageRatio: totalGroups > 0 ? groupsWithDocs / totalGroups : 0,
  undocumentedGroups
};

// ============================================
// K. Dependency Direction
// ============================================
const dependencyDirection = [];
const groupImportCounts = {};

interGroupImportsArray.forEach(imp => {
  const key = `${imp.from} -> ${imp.to}`;
  if (!groupImportCounts[key]) {
    groupImportCounts[key] = { dependent: imp.from, dependsOn: imp.to, count: 0 };
  }
  groupImportCounts[key].count += imp.count;
});

// Build dependency direction based on dominant flow
const pairCounts = {};
interGroupImportsArray.forEach(imp => {
  const forwardKey = `${imp.from} -> ${imp.to}`;
  const reverseKey = `${imp.to} -> ${imp.from}`;
  const existing = pairCounts[forwardKey] || 0;
  const reverseExisting = pairCounts[reverseKey] || 0;

  if (existing >= reverseExisting) {
    pairCounts[forwardKey] = existing + imp.count;
  }
});

Object.keys(pairCounts).forEach(key => {
  const [dependent, dependsOn] = key.split(' -> ');
  if (dependent !== dependsOn) {
    dependencyDirection.push({ dependent, dependsOn });
  }
});

// ============================================
// File Stats
// ============================================
const filesPerGroup = {};
Object.keys(directoryGroups).forEach(group => {
  filesPerGroup[group] = directoryGroups[group].length;
});

const nodeTypeCounts = {};
Object.keys(nodeTypeGroups).forEach(type => {
  nodeTypeCounts[type] = nodeTypeGroups[type].length;
});

// ============================================
// Build Output
// ============================================
const output = {
  scriptCompleted: true,
  directoryGroups,
  nodeTypeGroups,
  crossCategoryEdges: crossCategoryEdgesArray,
  interGroupImports: interGroupImportsArray,
  intraGroupDensity,
  patternMatches,
  deploymentTopology,
  dataPipeline,
  docCoverage,
  dependencyDirection,
  fileStats: {
    totalFileNodes: fileNodes.length,
    filesPerGroup,
    nodeTypeCounts
  },
  fileFanIn,
  fileFanOut
};

// Write output
try {
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2));
  console.log('Analysis completed successfully');
  console.log(`Total file nodes: ${fileNodes.length}`);
  console.log(`Directory groups: ${Object.keys(directoryGroups).length}`);
  console.log(`Node types: ${Object.keys(nodeTypeGroups).join(', ')}`);
} catch (e) {
  console.error('Error writing output file:', e.message);
  process.exit(1);
}

process.exit(0);
