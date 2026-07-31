import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { DocumentTree, TreeNode } from "../api";

interface TreeViewProps {
  tree: DocumentTree;
  highlightNodeId: string | null;
}

export function treeNodeDomId(nodeId: string): string {
  return `tree-node-${nodeId}`;
}

function NodeRow({ node, depth, highlighted }: { node: TreeNode; depth: number; highlighted: boolean }) {
  return (
    <div
      id={node.node_id != null ? treeNodeDomId(node.node_id) : undefined}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
      className={[
        "rounded-md py-1.5 pr-2 transition-colors",
        highlighted ? "bg-white/10 ring-2 ring-white/40" : "",
      ].join(" ")}
    >
      {node.node_id && <span className="mr-1.5 text-xs text-slate-500">{node.node_id}</span>}
      <span className="text-sm font-medium text-slate-200">{node.title}</span>
      {node.summary && <p className="mt-0.5 text-xs leading-snug text-slate-400">{node.summary}</p>}
    </div>
  );
}

function Node({ node, depth, highlightNodeId }: { node: TreeNode; depth: number; highlightNodeId: string | null }) {
  const [open, setOpen] = useState(true);
  const highlighted = node.node_id != null && node.node_id === highlightNodeId;

  // Leaf node: no collapsible wrapper needed.
  if (node.children.length === 0) {
    return (
      <li className="flex items-start gap-1.5" style={{ paddingLeft: "14px" }}>
        <span className="inline-block w-[14px] shrink-0" />
        <div className="min-w-0 flex-1">
          <NodeRow node={node} depth={depth} highlighted={highlighted} />
        </div>
      </li>
    );
  }

  return (
    <li>
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex items-start gap-1.5">
          <CollapsibleTrigger
            aria-label={open ? "Collapse section" : "Expand section"}
            className="mt-2 shrink-0 text-slate-500 hover:text-slate-200"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`transition-transform ${open ? "rotate-90" : ""}`}
            >
              <path d="m9 18 6-6-6-6" />
            </svg>
          </CollapsibleTrigger>
          <div className="min-w-0 flex-1">
            <NodeRow node={node} depth={depth} highlighted={highlighted} />
          </div>
        </div>
        <CollapsibleContent>
          <ul>
            {node.children.map((child, i) => (
              <Node key={child.node_id ?? i} node={child} depth={depth + 1} highlightNodeId={highlightNodeId} />
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </li>
  );
}

export default function TreeView({ tree, highlightNodeId }: TreeViewProps) {
  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-slate-200">{tree.title || "Document structure"}</h2>
      {tree.children.length === 0 ? (
        <p className="text-sm text-slate-500">No sections were detected in this document.</p>
      ) : (
        <ul>
          {tree.children.map((child, i) => (
            <Node key={child.node_id ?? i} node={child} depth={0} highlightNodeId={highlightNodeId} />
          ))}
        </ul>
      )}
    </div>
  );
}
