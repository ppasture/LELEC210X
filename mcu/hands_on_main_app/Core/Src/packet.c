/*
 * packet.c
 */

#include "aes_ref.h"
#include "config.h"
#include "packet.h"
#include "main.h"
#include "utils.h"
#include <string.h>
#include "aes.h"

// BUG : VSCode does not recognize the AES macro, so this is a quick fix, that does not impact the code
#ifndef AES
#define AES
#endif
#include "stm32l4xx_hal_cryp.h"
#include "stm32l4xx_hal_cryp_ex.h"

// BUG : VSCode does not recognize many of the types, such as uint32_t, i couldn't find a fix for this

void tag_cbc_mac_hardware(uint8_t *tag, const uint8_t *msg, size_t msg_len) {
    // Allocate enough space for all blocks
    __ALIGN_BEGIN static uint8_t *tmp_out = NULL;

    // Calculate number of blocks needed (rounded up)
    size_t num_blocks = (msg_len + 15) / 16;
    size_t total_size = num_blocks * 16;

    // Allocate memory for all blocks
    tmp_out = malloc(total_size);
    if (tmp_out == NULL) {
        Error_Handler();
        return;
    }

	// Step 1: Reset the peripheral (but its donne by HAL_CRYP_AESCBC_Encrypt)

    // Step 3: Perform CBC encryption with proper padding
    if (HAL_CRYP_AESCBC_Encrypt(&hcryp, (uint8_t *)msg, msg_len, tmp_out, 1000) != HAL_OK) {
        free(tmp_out);
        Error_Handler();
        return;
    }

    // Step 4: Copy the last block as the MAC
    memcpy(tag, tmp_out + ((num_blocks - 1) * 16), 16);

    // Clean up
    free(tmp_out);
}

// Assumes payload is already in place in the packet
int make_packet(uint8_t *packet, size_t payload_len, uint8_t sender_id, uint32_t serial) {
    size_t packet_len = payload_len + PACKET_HEADER_LENGTH + PACKET_TAG_LENGTH;
    // So is the tag
	memset(packet + payload_len + PACKET_HEADER_LENGTH, 0, PACKET_TAG_LENGTH);

	// Set the reserved field to 0
	packet[0] = 0x00;
	// Set the emitter_id field
	packet[1] = sender_id;
	// Set the payload_length field
	packet[2] = (payload_len >> 8) & 0xFF;
	packet[3] = payload_len & 0xFF;
	// Set the packet_serial field
	packet[4] = (serial >> 24) & 0xFF;
	packet[5] = (serial >> 16) & 0xFF;
	packet[6] = (serial >> 8) & 0xFF;
	packet[7] = serial & 0xFF;

	//			setting the packet header with the following structure :
	/***************************************************************************
	 *    Field       	Length (bytes)      Encoding        Description
	 ***************************************************************************
	 *  r 					1 								Reserved, set to 0.
	 * 	emitter_id 			1 					BE 			Unique id of the sensor node.
	 *	payload_length 		2 					BE 			Length of app_data (in bytes).
	 *	packet_serial 		4 					BE 			Unique and incrementing id of the packet.
	 *	app_data 			any 							The feature vectors.
	 *	tag 				16 								Message authentication code (MAC).
	 *
	 *	Note : BE refers to Big endian
	 *		 	Use the structure 	packet[x] = y; 	to set a byte of the packet buffer
	 *		 	To perform bit masking of the specific bytes you want to set, you can use
	 *		 		- bitshift operator (>>),
	 *		 		- and operator (&) with hex value, e.g.to perform 0xFF
	 *		 	This will be helpful when setting fields that are on multiple bytes.
	*/
	tag_cbc_mac_hardware(packet + payload_len + PACKET_HEADER_LENGTH, packet, payload_len + PACKET_HEADER_LENGTH);
    return packet_len;
}
