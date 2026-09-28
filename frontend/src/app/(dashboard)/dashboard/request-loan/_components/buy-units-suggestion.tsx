"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

interface BuyUnitsSuggestionProps {
  message: string;
  onClose: () => void;
}

export default function BuyUnitsSuggestion({ message, onClose }: BuyUnitsSuggestionProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div 
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Dialog Content */}
      <div className="relative z-50 w-full max-w-md">
        <div className="bg-background rounded-lg shadow-xl border overflow-hidden">
          {/* Header */}
          <div className="flex items-center p-6 border-b">
            <div className="flex items-center justify-center w-12 h-12 bg-yellow-100 rounded-full mr-4">
              <AlertTriangle className="h-6 w-6 text-yellow-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-foreground">Loan Review</h2>
              <p className="text-sm text-muted-foreground">Your application needs attention</p>
            </div>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            <div className="space-y-3">
              <p className="text-muted-foreground leading-relaxed">
                {message || "Your loan application couldn't be approved at this time."}
              </p>
              
              <div className="bg-muted/50 p-3 rounded-md text-sm">
                <h4 className="font-medium mb-2">Next Steps:</h4>
                <ul className="text-muted-foreground space-y-1 text-sm">
                  <li>• Improve your payment consistency</li>
                  <li>• Reduce disconnections by buying units regularly</li>
                  <li>• Consider a smaller loan amount next time</li>
                </ul>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <Button 
                variant="outline" 
                onClick={onClose}
                className="flex-1"
              >
                Close
              </Button>
              <Button 
                asChild
                className="flex-1"
              >
                <Link href="/dashboard/buy-units" onClick={onClose}>
                  Buy Units Now
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}