#include <assert.h>
#include <stdint.h>
#include "BuzzerCore.h"

int main() {
  gpawa::NonBlockingBuzzer buzzer;
  const uint32_t start = UINT32_MAX - 40;
  buzzer.start(2, start);
  assert(buzzer.tick(start + 89U));
  assert(!buzzer.tick(start + 90U));
  assert(buzzer.active());
  assert(buzzer.tick(start + 180U));
  assert(buzzer.active());
  assert(!buzzer.tick(start + 270U));
  assert(!buzzer.active());

  gpawa::EmptyCreditReminder reminder;
  const uint32_t exhaustedAt = UINT32_MAX - 60000U;
  assert(!reminder.tick(exhaustedAt, true, false));
  assert(!reminder.tick(exhaustedAt + 119999U, true, false));
  assert(reminder.tick(exhaustedAt + 120000U, true, false));
  assert(!reminder.tick(exhaustedAt + 240000U, true, true));
  assert(reminder.tick(exhaustedAt + 240001U, true, false));
  assert(!reminder.tick(exhaustedAt + 240002U, false, false));
  assert(!reminder.tick(exhaustedAt + 240003U, true, false));
  assert(!reminder.tick(exhaustedAt + 360002U, true, false));
  assert(reminder.tick(exhaustedAt + 360003U, true, false));
  return 0;
}
