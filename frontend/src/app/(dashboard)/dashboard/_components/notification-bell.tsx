"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bell, CheckCheck, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { get, patch } from "@/lib/fetch-client";

interface MeterNotification {
  id: number;
  notification_type: string;
  units_kwh: number;
  occurred_at: string;
  is_read: boolean;
  message: string;
  meter_no: string | null;
  meter_label: string | null;
}

interface NotificationsResponse {
  success: boolean;
  notifications: MeterNotification[];
  unread_count: number;
}

const POLL_MS = 15_000;

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [marking, setMarking] = useState(false);
  const [notifications, setNotifications] = useState<MeterNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<NotificationsResponse>("meter/notifications/");
      if (!res.error && res.data?.success) {
        setNotifications(res.data.notifications ?? []);
        setUnreadCount(res.data.unread_count ?? 0);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const timer = window.setInterval(fetchNotifications, POLL_MS);
    return () => window.clearInterval(timer);
  }, [fetchNotifications]);

  useEffect(() => {
    if (open) {
      fetchNotifications();
    }
  }, [open, fetchNotifications]);

  async function markAllRead() {
    setMarking(true);
    try {
      const res = await patch<{ success: boolean }>("meter/notifications/", { all: true });
      if (!res.error && res.data?.success) {
        setUnreadCount(0);
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      }
    } finally {
      setMarking(false);
    }
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" className="relative shrink-0">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -right-1 -top-1 h-5 min-w-5 px-1 text-[10px] font-bold"
            >
              {unreadCount > 9 ? "9+" : unreadCount}
            </Badge>
          )}
          <span className="sr-only">Meter notifications</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 sm:w-96">
        <div className="flex items-center justify-between px-2 py-1.5">
          <DropdownMenuLabel className="p-0">Alerts</DropdownMenuLabel>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={markAllRead}
              disabled={marking}
            >
              {marking ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <>
                  <CheckCheck className="h-3.5 w-3.5 mr-1" />
                  Mark all read
                </>
              )}
            </Button>
          )}
        </div>
        <DropdownMenuSeparator />
        {loading && notifications.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Loading…
          </div>
        ) : notifications.length === 0 ? (
          <p className="px-3 py-6 text-sm text-center text-muted-foreground">
            No meter alerts yet. Low-units warnings from ThingsBoard will appear here.
          </p>
        ) : (
          <div className="max-h-72 overflow-y-auto">
            {notifications.map((n) => (
              <DropdownMenuItem
                key={n.id}
                className="flex flex-col items-start gap-1 py-2.5 cursor-default focus:bg-muted"
                onSelect={(e) => e.preventDefault()}
              >
                <div className="flex w-full items-start justify-between gap-2">
                  <span className="text-sm font-medium leading-snug">
                    {n.meter_no
                      ? `Meter ${n.meter_no}${n.meter_label ? ` (${n.meter_label})` : ""}`
                      : "Meter alert"}
                  </span>
                  {!n.is_read && (
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-blue-600" />
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  {n.notification_type === "LOW_UNITS"
                    ? `${n.units_kwh.toFixed(2)} kWh remaining`
                    : "Account update"}{" "}
                  · {formatWhen(n.occurred_at)}
                </span>
                {n.message && (
                  <span className="text-xs text-muted-foreground line-clamp-2">{n.message}</span>
                )}
              </DropdownMenuItem>
            ))}
          </div>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/dashboard/tokens" className="w-full cursor-pointer">
            Open meters — check units or top up
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

}
