/* Dump Mixamo/FBX skeletal animation as JSON for the Brutal Fist .x bridge. */
#include "ufbx.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void sanitize(char *dst, const char *src, size_t n) {
  size_t j = 0;
  for (size_t i = 0; src[i] && j + 1 < n; i++) {
    char c = src[i];
    if (c == ':' || c == ' ' || c == '.' || c == '|' || c == '-' || c == '/')
      c = '_';
    dst[j++] = c;
  }
  dst[j] = 0;
}

static int looks_like_bone(const ufbx_node *node) {
  const char *name = node->name.data ? node->name.data : "";
  if (node->bone) return 1;
  if (strstr(name, "mixamorig")) return 1;
  if (strstr(name, "Hips") || strstr(name, "Spine") || strstr(name, "Armature"))
    return 1;
  if (strstr(name, "Head") || strstr(name, "Neck") || strstr(name, "Leg") ||
      strstr(name, "Arm") || strstr(name, "Hand") || strstr(name, "Foot"))
    return 1;
  return 0;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: fbx_dump_anim file.fbx\n");
    return 1;
  }

  ufbx_load_opts opts = {0};
  opts.target_axes = ufbx_axes_right_handed_y_up;
  opts.target_unit_meters = 1.0f;
  opts.ignore_geometry = true;
  opts.evaluate_skinning = false;

  ufbx_error err;
  ufbx_scene *scene = ufbx_load_file(argv[1], &opts, &err);
  if (!scene) {
    fprintf(stderr, "load failed: %s\n", err.description.data);
    return 2;
  }

  ufbx_anim *anim = scene->anim;
  double t0 = anim ? anim->time_begin : 0.0;
  double t1 = anim ? anim->time_end : 0.0;
  if (t1 <= t0 + 1e-6) t1 = t0 + 1.0 / 30.0;
  const double fps = 30.0;
  int frames = (int)floor((t1 - t0) * fps + 0.5);
  if (frames < 1) frames = 1;

  size_t bone_count = 0;
  for (size_t i = 0; i < scene->nodes.count; i++) {
    if (looks_like_bone(scene->nodes.data[i])) bone_count++;
  }

  printf("{\n");
  printf("  \"duration\": %.6f,\n", t1 - t0);
  printf("  \"fps\": 30,\n");
  printf("  \"frames\": %d,\n", frames);
  printf("  \"boneCount\": %zu,\n", bone_count);
  printf("  \"bones\": {\n");

  int first = 1;
  for (size_t i = 0; i < scene->nodes.count; i++) {
    ufbx_node *node = scene->nodes.data[i];
    if (!looks_like_bone(node)) continue;
    const char *name = node->name.data ? node->name.data : "unnamed";
    char san[256];
    sanitize(san, name, sizeof san);

    if (!first) printf(",\n");
    first = 0;
    printf("    \"%s\": {\n", san);
    printf("      \"r\": [");
    for (int f = 0; f <= frames; f++) {
      double t = t0 + (double)f / fps;
      if (t > t1) t = t1;
      ufbx_transform tr = ufbx_evaluate_transform(anim, node, t);
      if (f) printf(",");
      printf("[%.6f,%.6f,%.6f,%.6f]", tr.rotation.x, tr.rotation.y,
             tr.rotation.z, tr.rotation.w);
    }
    printf("],\n");
    printf("      \"t\": [");
    for (int f = 0; f <= frames; f++) {
      double t = t0 + (double)f / fps;
      if (t > t1) t = t1;
      ufbx_transform tr = ufbx_evaluate_transform(anim, node, t);
      if (f) printf(",");
      printf("[%.6f,%.6f,%.6f]", tr.translation.x, tr.translation.y,
             tr.translation.z);
    }
    printf("]\n    }");
  }
  printf("\n  }\n}\n");
  ufbx_free_scene(scene);
  return 0;
}
