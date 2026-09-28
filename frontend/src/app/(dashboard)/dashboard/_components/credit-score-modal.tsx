"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { 
  X, 
  TrendingUp, 
  TrendingDown, 
  Award, 
  Clock, 
  Wallet, 
  Share2, 
  CreditCard,
  Zap,
  Brain,
  Target,
  BarChart3,
  ChevronLeft,
  Star,
  Activity,
  Shield
} from "lucide-react";
import { get } from "@/lib/fetch";
import { cn } from "@/lib/utils";

interface CreditScoreModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface CreditScoreData {
  overall_score: number;
  base_score: number;
  behavioral_bonus: number;
  components: {
    payment_history: number;
    wallet_usage: number;
    purchase_activity: number;
    sharing_behavior: number;
    loan_history: number;
  };
  history: Array<{
    previous_score: number;
    new_score: number;
    change_amount: number;
    reason: string;
    event_type: string;
    created_at: string;
  }>;
}

export default function CreditScoreModal({ isOpen, onClose }: CreditScoreModalProps) {
  const [data, setData] = useState<CreditScoreData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen) {
      fetchCreditScore();
    }
  }, [isOpen]);

  const fetchCreditScore = async () => {
    setLoading(true);
    try {
      const response = await get("loans/credit-score/");
      if (!response.error && response.data) {
        setData(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch credit score:", error);
    } finally {
      setLoading(false);
    }
  };

  // Handle escape key press
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  // Handle click outside
  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-yellow-600";
    return "text-red-600";
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 80) return "bg-green-100";
    if (score >= 60) return "bg-yellow-100";
    return "bg-red-100";
  };

  const getScoreGrade = (score: number) => {
    if (score >= 90) return { grade: "Excellent", icon: "👑", description: "Top creditworthiness - You qualify for the best rates!" };
    if (score >= 80) return { grade: "Very Good", icon: "⭐", description: "Strong credit profile - Great loan terms available" };
    if (score >= 70) return { grade: "Good", icon: "👍", description: "Solid credit standing - Good loan options" };
    if (score >= 60) return { grade: "Fair", icon: "📊", description: "Average credit rating - Building positive history" };
    if (score >= 50) return { grade: "Needs Improvement", icon: "⚠️", description: "Room for growth - Keep making timely payments" };
    return { grade: "Poor", icon: "🔴", description: "Requires attention - Focus on improving your habits" };
  };

  const getTierInfo = (score: number) => {
    if (score >= 90) return { tier: "Platinum", color: "bg-purple-500", textColor: "text-purple-700", max_amount: 200000, interest_rate: "9%" };
    if (score >= 80) return { tier: "Gold", color: "bg-yellow-500", textColor: "text-yellow-700", max_amount: 150000, interest_rate: "10%" };
    if (score >= 70) return { tier: "Silver", color: "bg-gray-400", textColor: "text-gray-700", max_amount: 100000, interest_rate: "11%" };
    if (score >= 60) return { tier: "Bronze", color: "bg-amber-600", textColor: "text-amber-700", max_amount: 50000, interest_rate: "12%" };
    return { tier: "Not Eligible", color: "bg-gray-300", textColor: "text-gray-500", max_amount: 0, interest_rate: "N/A" };
  };

  if (!isOpen) return null;

  const overallScore = data?.overall_score || 0;
  const baseScore = data?.base_score || 0;
  const behavioralBonus = data?.behavioral_bonus || 0;
  const tierInfo = getTierInfo(overallScore);

  return (
    <div 
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto relative">
        {/* Close button - Top Right */}
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-2 h-8 w-8 rounded-full hover:bg-gray-100 z-10"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>

        <CardHeader className="text-center pb-4">
          <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-r from-blue-500 to-blue-600 rounded-full mb-3 mx-auto">
            <Brain className="h-8 w-8 text-white" />
          </div>
          <CardTitle className="text-xl">Your Credit Score</CardTitle>
          <CardDescription>
            Your overall creditworthiness based on third-party data and your activity
          </CardDescription>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="py-12 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-muted-foreground">Loading credit score...</p>
            </div>
          ) : (
            <>
              {/* Main Score Display */}
              <div className="text-center mb-6 p-6 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100">
                <div className={`inline-flex items-center justify-center w-36 h-36 rounded-full ${getScoreBgColor(overallScore)} mb-4`}>
                  <span className={`text-6xl font-bold ${getScoreColor(overallScore)}`}>
                    {overallScore}
                  </span>
                </div>
                <div className="text-xl font-semibold">
                  {getScoreGrade(overallScore).grade}
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  {getScoreGrade(overallScore).description}
                </div>
                <Progress value={overallScore} className="mt-4 h-3" />
              </div>

              {/* Score Breakdown */}
              <div className="mb-6 grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-blue-50 text-center">
                  <div className="flex items-center justify-center gap-1 mb-2">
                    <Shield className="h-4 w-4 text-blue-600" />
                    <span className="text-xs font-medium text-blue-600">Base Score</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-700">{baseScore}</div>
                  <div className="text-xs text-blue-600 mt-1">From third-party data</div>
                </div>
                <div className="p-4 rounded-lg bg-green-50 text-center">
                  <div className="flex items-center justify-center gap-1 mb-2">
                    <Star className="h-4 w-4 text-green-600" />
                    <span className="text-xs font-medium text-green-600">Behavior Bonus</span>
                  </div>
                  <div className="text-2xl font-bold text-green-700">+{behavioralBonus}</div>
                  <div className="text-xs text-green-600 mt-1">From your activity</div>
                </div>
              </div>

              {/* Formula Explanation */}
              <div className="mb-6 p-3 bg-gray-50 rounded-lg text-center">
                <p className="text-xs text-gray-600">
                  <span className="font-medium">Formula:</span> Base Score ({baseScore}) + Behavior Bonus (+{behavioralBonus}) = <span className="font-bold">{overallScore}</span>
                </p>
              </div>

              {/* Loan Tier Information */}
              <div className={`mb-6 p-4 rounded-lg ${tierInfo.color} bg-opacity-10`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Current Loan Tier</span>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium text-white ${tierInfo.color}`}>
                    {tierInfo.tier}
                  </span>
                </div>
                {tierInfo.max_amount > 0 ? (
                  <>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-sm">Maximum Loan Amount</span>
                      <span className="text-lg font-bold">UGX {tierInfo.max_amount.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-sm">Interest Rate</span>
                      <span className="text-md font-semibold">{tierInfo.interest_rate}</span>
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-center mt-2">
                    Continue building your credit history to qualify for loans
                  </div>
                )}
              </div>

              {/* Score Components */}
              <div className="mb-6">
                <h4 className="font-semibold text-sm mb-3 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  What Affects Your Score?
                </h4>
                
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center gap-1">
                        <CreditCard className="h-3 w-3" />
                        Payment History
                      </span>
                      <span className="font-medium">{data?.components.payment_history}%</span>
                    </div>
                    <Progress value={data?.components.payment_history} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">On-time payments build trust</p>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center gap-1">
                        <Wallet className="h-3 w-3" />
                        Wallet Usage
                      </span>
                      <span className="font-medium">{data?.components.wallet_usage}%</span>
                    </div>
                    <Progress value={data?.components.wallet_usage} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">Using wallet shows financial responsibility</p>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center gap-1">
                        <Target className="h-3 w-3" />
                        Purchase Activity
                      </span>
                      <span className="font-medium">{data?.components.purchase_activity}%</span>
                    </div>
                    <Progress value={data?.components.purchase_activity} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">Regular purchases show engagement</p>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center gap-1">
                        <Share2 className="h-3 w-3" />
                        Sharing Behavior
                      </span>
                      <span className="font-medium">{data?.components.sharing_behavior}%</span>
                    </div>
                    <Progress value={data?.components.sharing_behavior} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">Sharing units builds community trust</p>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Loan History
                      </span>
                      <span className="font-medium">{data?.components.loan_history}%</span>
                    </div>
                    <Progress value={data?.components.loan_history} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">Successful loan completion is key</p>
                  </div>
                </div>
              </div>

              {/* Recent History */}
              {data?.history && data.history.length > 0 && (
                <div className="mb-6">
                  <h4 className="font-semibold text-sm mb-3 flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Recent Score Changes
                  </h4>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {data.history.slice(0, 8).map((item, idx) => (
                      <div key={idx} className="text-xs flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                        {item.change_amount > 0 ? (
                          <TrendingUp className="h-3 w-3 text-green-500 mt-0.5 flex-shrink-0" />
                        ) : (
                          <TrendingDown className="h-3 w-3 text-red-500 mt-0.5 flex-shrink-0" />
                        )}
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{item.reason}</p>
                          <div className="flex justify-between mt-1">
                            <span className={`text-xs ${item.change_amount > 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {item.change_amount > 0 ? '+' : ''}{item.change_amount} points
                            </span>
                            <span className="text-gray-400">
                              {new Date(item.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tips to Improve */}
              <div className="p-4 bg-gradient-to-r from-yellow-50 to-orange-50 rounded-lg">
                <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-yellow-600" />
                  How to Improve Your Score
                </h4>
                <ul className="text-xs space-y-1 text-gray-700">
                  <li>✓ Make loan payments on or before the due date</li>
                  <li>✓ Use your wallet for transactions instead of direct payments</li>
                  <li>✓ Purchase units regularly to show consistent activity</li>
                  <li>✓ Share units with others to build community trust</li>
                  <li>✓ Complete loans successfully to build history</li>
                </ul>
              </div>

              {/* Info Note */}
              <div className="mt-4 text-xs text-center text-muted-foreground">
                <p>Your credit score updates in real-time based on your activity</p>
                <p>Higher scores unlock better loan terms and higher limits</p>
              </div>

              {/* Close button at bottom */}
              <div className="mt-6 flex justify-center">
                <Button
                  variant="outline"
                  onClick={onClose}
                  className="gap-2 px-6"
                >
                  Close
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}