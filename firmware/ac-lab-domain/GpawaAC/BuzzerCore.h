#pragma once
#include <stdint.h>

namespace gpawa {
class NonBlockingBuzzer {
 public:
  void start(uint8_t count, uint32_t now) {
    if (!count) return;
    remaining_ = count;
    high_ = true;
    changedAt_ = now;
  }

  bool tick(uint32_t now) {
    if (remaining_ && uint32_t(now - changedAt_) >= PULSE_MS) {
      changedAt_ = now;
      high_ = !high_;
      if (!high_) --remaining_;
    }
    return high_;
  }

  bool active() const { return remaining_ != 0; }

 private:
  static constexpr uint32_t PULSE_MS = 90;
  uint32_t changedAt_ = 0;
  uint8_t remaining_ = 0;
  bool high_ = false;
};

class EmptyCreditReminder {
 public:
  bool tick(uint32_t now, bool depleted, bool buzzerBusy) {
    if (!depleted) {
      seen_ = false;
      return false;
    }
    if (!seen_) {
      seen_ = true;
      lastReminderAt_ = now;
      return false;
    }
    if (!buzzerBusy && uint32_t(now - lastReminderAt_) >= REMINDER_MS) {
      lastReminderAt_ = now;
      return true;
    }
    return false;
  }

 private:
  static constexpr uint32_t REMINDER_MS = 120000;
  uint32_t lastReminderAt_ = 0;
  bool seen_ = false;
};
}
