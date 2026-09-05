<?php
/**
 * Plugin Name: Boost Rankers SEO Bridge
 * Description: Secure REST bridge that lets Boost Rankers AI SEO OS write Yoast SEO title, meta description and focus keyphrase for WordPress posts.
 * Version: 1.0.0
 * Author: Boost Rankers
 * License: GPL-2.0-or-later
 */

if (!defined('ABSPATH')) {
    exit;
}

function br_seo_bridge_yoast_active(): bool {
    return defined('WPSEO_VERSION') || class_exists('WPSEO_Options');
}

add_action('rest_api_init', function () {
    register_rest_route('boost-rankers/v1', '/seo-meta/status', [
        'methods' => WP_REST_Server::READABLE,
        'permission_callback' => function () {
            return current_user_can('edit_posts');
        },
        'callback' => function () {
            return rest_ensure_response([
                'success' => true,
                'plugin' => 'boost-rankers-seo-bridge',
                'version' => '1.0.0',
                'yoast_active' => br_seo_bridge_yoast_active(),
            ]);
        },
    ]);

    register_rest_route('boost-rankers/v1', '/seo-meta/(?P<id>\d+)', [
        'methods' => WP_REST_Server::CREATABLE,
        'permission_callback' => function (WP_REST_Request $request) {
            $post_id = (int) $request['id'];
            return $post_id > 0 && current_user_can('edit_post', $post_id);
        },
        'args' => [
            'seo_title' => [
                'required' => true,
                'type' => 'string',
                'sanitize_callback' => 'sanitize_text_field',
            ],
            'meta_description' => [
                'required' => true,
                'type' => 'string',
                'sanitize_callback' => 'sanitize_textarea_field',
            ],
            'focus_keyphrase' => [
                'required' => true,
                'type' => 'string',
                'sanitize_callback' => 'sanitize_text_field',
            ],
        ],
        'callback' => function (WP_REST_Request $request) {
            $post_id = (int) $request['id'];

            if (!get_post($post_id)) {
                return new WP_Error(
                    'br_post_not_found',
                    'WordPress post not found.',
                    ['status' => 404]
                );
            }

            if (!br_seo_bridge_yoast_active()) {
                return new WP_Error(
                    'br_yoast_not_active',
                    'Yoast SEO is not active on this WordPress site.',
                    ['status' => 424]
                );
            }

            update_post_meta($post_id, '_yoast_wpseo_title', $request->get_param('seo_title'));
            update_post_meta($post_id, '_yoast_wpseo_metadesc', $request->get_param('meta_description'));
            update_post_meta($post_id, '_yoast_wpseo_focuskw', $request->get_param('focus_keyphrase'));

            // Trigger WordPress/Yoast post-save processing so indexable data can
            // be refreshed instead of requiring a manual WP editor save.
            wp_update_post(['ID' => $post_id]);
            clean_post_cache($post_id);

            return rest_ensure_response([
                'success' => true,
                'post_id' => $post_id,
                'yoast' => [
                    'title' => get_post_meta($post_id, '_yoast_wpseo_title', true),
                    'meta_description' => get_post_meta($post_id, '_yoast_wpseo_metadesc', true),
                    'focus_keyphrase' => get_post_meta($post_id, '_yoast_wpseo_focuskw', true),
                ],
            ]);
        },
    ]);
});
