// Tiny payload: show the text of /data/toast.txt as a PS5 toast notification.
// Send to elfldr (:9021) after uploading the text file; it prints once and exits.
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  int32_t type, req_id, priority, msg_id, target_id, user_id, unk1, unk2, app_id,
      error_num, unk3;
  char use_icon_image_uri;
  char message[1024];
  char uri[1024];
  char unkstr[1024];
} NotifyReq; // 0xC30, same layout as libhijacker/onionHEN notify.hpp

extern "C" int sceKernelSendNotificationRequest(int, NotifyReq *, size_t, int);

int main() {
  NotifyReq req{};
  FILE *f = fopen("/data/toast.txt", "r");
  size_t n = f ? fread(req.message, 1, sizeof(req.message) - 1, f) : 0;
  if (f) fclose(f);
  if (!n) strcpy(req.message, "toast.txt missing");
  while (n && (req.message[n - 1] == '\n' || req.message[n - 1] == '\r')) req.message[--n] = 0;
  return sceKernelSendNotificationRequest(0, &req, sizeof(req), 0) < 0;
}
