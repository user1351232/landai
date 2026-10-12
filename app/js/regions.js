// 지역 설정 — config/regions/*.yaml 과 같은 값 (값을 바꿀 때는 두 곳 모두 고치세요)
export const REGIONS = {
  jeonju: {
    id: "jeonju", name: "전주시", sido_code: "52", legacy_sido_code: "45",
    bbox_wgs84: [126.98, 35.72, 127.25, 35.93], center: [127.148, 35.8242],
  },
  wanju: {
    id: "wanju", name: "완주군", sido_code: "52", legacy_sido_code: "45",
    bbox_wgs84: [126.95, 35.70, 127.50, 36.15], center: [127.162, 35.9047],
  },
};
