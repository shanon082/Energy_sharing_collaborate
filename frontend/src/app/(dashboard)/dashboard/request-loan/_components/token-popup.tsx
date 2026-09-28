"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface TokenPopupProps {
  token: string;
  units: number;
  onClose: () => void;
}

export default function TokenPopup({ token, units, onClose }: TokenPopupProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy token:', err);
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = token;
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Dialog Content */}
      <div className="relative z-50 w-full max-w-sm">
        <div className="bg-background rounded-lg shadow-xl border overflow-hidden">
          {/* Header */}
          <div className="flex items-center p-6 border-b">
            <div className="flex items-center justify-center w-12 h-12 bg-green-100 rounded-full mr-4">
              <Zap className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-foreground">Token Generated</h2>
              <p className="text-sm text-muted-foreground">Your loan has been disbursed</p>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            <div className="text-center">
              <div className="text-4xl font-bold text-green-600 mb-2">{units}</div>
              <p className="text-sm text-muted-foreground">Units available through this token</p>
            </div>

            <div className="bg-muted/50 p-4 rounded-lg border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Meter Token</span>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={copyToClipboard}
                  className="h-8 w-8 p-0"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <div className="flex items-center justify-center">
                <code className="bg-muted text-lg font-mono font-bold px-3 py-2 rounded tracking-wider text-center break-all">
                  {token}
                </code>
              </div>
              <p className="text-xs text-muted-foreground text-center mt-2">
                Enter this code on your meter keypad
              </p>
            </div>

            <div className="text-xs text-muted-foreground text-center space-y-1">
              <p>Token expires in 30 days</p>
              <p>Confirm the amount shown on your meter before pressing enter</p>
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <Button 
                variant="outline" 
                onClick={onClose}
                className="flex-1"
              >
                Done
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
