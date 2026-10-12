// 윈도우에서 실행할 때 검은 콘솔 창이 뜨지 않게 함
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    landai_lib::run()
}
