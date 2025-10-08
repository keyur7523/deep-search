"use client";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { AgentMode, RoutingExplanation } from "@/lib/types";

interface ResearchModeToggleProps {
  value: AgentMode;
  onChange: (mode: AgentMode) => void;
  explanation?: RoutingExplanation;
  disabled?: boolean;
}

export function ResearchModeToggle({
  value,
  onChange,
  explanation,
  disabled = false
}: ResearchModeToggleProps) {
  return (
    <div className="space-y-3">
      <Label className="text-sm font-medium">Research Mode</Label>
      
      <RadioGroup 
        value={value} 
        onValueChange={onChange}
        disabled={disabled}
      >
        <div className="flex items-start space-x-3 rounded-md border p-3 hover:bg-accent/50 transition-colors">
          <RadioGroupItem value="auto" id="auto" className="mt-0.5" />
          <div className="flex-1">
            <Label htmlFor="auto" className="font-medium cursor-pointer">
              Auto (Recommended)
            </Label>
            <p className="text-sm text-muted-foreground mt-1">
              System automatically decides based on topic complexity
            </p>
          </div>
        </div>
        
        <div className="flex items-start space-x-3 rounded-md border p-3 hover:bg-accent/50 transition-colors">
          <RadioGroupItem value="simple" id="simple" className="mt-0.5" />
          <div className="flex-1">
            <Label htmlFor="simple" className="font-medium cursor-pointer">
              Simple
            </Label>
            <p className="text-sm text-muted-foreground mt-1">
              Fast, linear research pipeline for straightforward topics
            </p>
          </div>
        </div>
        
        <div className="flex items-start space-x-3 rounded-md border p-3 hover:bg-accent/50 transition-colors">
          <RadioGroupItem value="agentic" id="agentic" className="mt-0.5" />
          <div className="flex-1">
            <Label htmlFor="agentic" className="font-medium cursor-pointer">
              Agentic
            </Label>
            <p className="text-sm text-muted-foreground mt-1">
              Deep, iterative research with quality gates and refinement
            </p>
          </div>
        </div>
      </RadioGroup>
      
      {explanation && value === "auto" && (
        <div className="rounded-md bg-muted p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              Selected Mode: <span className="capitalize">{explanation.mode}</span>
            </span>
            <span className="text-xs text-muted-foreground">
              Score: {explanation.score.toFixed(3)}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {explanation.reasoning}
          </p>
        </div>
      )}
    </div>
  );
}