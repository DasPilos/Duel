shader_type canvas_item;

// Затемнение и размытие сцены за выбором персонажа: копия экрана берётся с уровня mip и приглушается.
uniform sampler2D screen_texture : hint_screen_texture, filter_linear_mipmap;
uniform float blur_lod = 0.0;
uniform vec4 veil_color : source_color = vec4(0.05, 0.06, 0.09, 0.0);

void fragment() {
	vec3 behind = textureLod(screen_texture, SCREEN_UV, blur_lod).rgb;
	COLOR = vec4(mix(behind, veil_color.rgb, veil_color.a), 1.0);
}
